import logging
import time
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from socket import IPPROTO_TCP, TCP_NODELAY, socket
from threading import Thread
from typing import Optional

from rlbot import flat
from rlbot.utils.logging import get_logger

MAX_SIZE_2_BYTES = 2**16 - 1
# The default IP to connect to RLBotServer on
RLBOT_SERVER_IP = "127.0.0.1"
# The default port we can expect RLBotServer to be listening on
RLBOT_SERVER_PORT = 23234


class MsgHandlingResult(IntEnum):
    TERMINATED = 0
    NO_INCOMING_MSGS = 1
    MORE_MSGS_QUEUED = 2


class SocketRelay:
    """
    The SocketRelay provides an abstraction over the direct communication with
    the RLBotServer making it easy to send the various types of messages.

    Common use patterns are covered by `bot.py`, `script.py`, `hivemind.py`, and `match.py`
    from `rlbot.managers`.
    """

    is_connected = False
    _running = False
    """Indicates whether a messages are being handled by the `run` loop (potentially in a background thread)"""

    on_connect_handlers: list[Callable[[], None]] = []
    packet_handlers: list[Callable[[flat.GamePacket], None]] = []
    field_info_handlers: list[Callable[[flat.FieldInfo], None]] = []
    match_config_handlers: list[Callable[[flat.MatchConfiguration], None]] = []
    match_comm_handlers: list[Callable[[flat.MatchComm], None]] = []
    ball_prediction_handlers: list[Callable[[flat.BallPrediction], None]] = []
    controllable_team_info_handlers: list[
        Callable[[flat.ControllableTeamInfo], None]
    ] = []
    rendering_status_handlers: list[Callable[[flat.RenderingStatus], None]] = []
    raw_handlers: list[Callable[[flat.CoreMessage], None]] = []

    def __init__(
        self,
        agent_id: str,
        connection_timeout: float = 120,
        logger: Optional[logging.Logger] = None,
    ):
        self.agent_id = agent_id
        self.connection_timeout = connection_timeout
        self.logger = get_logger("interface") if logger is None else logger

        self.socket = socket()

        # Allow sending packets before getting a response from core
        self.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)

    def __del__(self):
        self.socket.close()

    @staticmethod
    def _int_to_bytes(val: int) -> bytes:
        return val.to_bytes(2, byteorder="big")

    def _read_int(self) -> int:
        return int.from_bytes(self._read_exact(2), "big")

    def _read_exact(self, n: int) -> bytes:
        buff = bytearray(n)
        view = memoryview(buff)

        pos = 0
        while pos < n:
            cr = self.socket.recv_into(view[pos:])
            if cr == 0:
                raise EOFError
            pos += cr
        return bytes(buff)

    def read_message(self) -> bytes:
        size = self._read_int()
        return self._read_exact(size)

    def send_bytes(self, data: bytes):
        assert self.is_connected, "Connection has not been established"

        size = len(data)
        if size > MAX_SIZE_2_BYTES:
            self.logger.error("Couldn't send message because it was too big!")
            return

        message = self._int_to_bytes(size) + data
        self.socket.sendall(message)

    def send_msg(
        self,
        msg: (
            flat.DisconnectSignal
            | flat.StartCommand
            | flat.MatchConfiguration
            | flat.PlayerInput
            | flat.DesiredGameState
            | flat.RenderGroup
            | flat.RemoveRenderGroup
            | flat.MatchComm
            | flat.ConnectionSettings
            | flat.StopCommand
            | flat.SetLoadout
            | flat.InitComplete
            | flat.RenderingStatus
        ),
    ):
        self.send_bytes(flat.InterfacePacket(msg).pack())

    def stop_match(self, shutdown_server: bool = False):
        self.send_msg(flat.StopCommand(shutdown_server))

    def start_match(self, match_config: Path | flat.MatchConfiguration):
        self.logger.info("Python interface is attempting to start match...")

        match match_config:
            case Path() as path:
                string_path = str(path.absolute().resolve())
                flatbuffer = flat.StartCommand(string_path)
            case flat.MatchConfiguration() as settings:
                flatbuffer = settings
            case _:
                raise ValueError(
                    "Expected MatchConfiguration or path to match config toml file"
                )

        self.send_msg(flatbuffer)

    def connect(
        self,
        *,
        wants_match_communications: bool,
        wants_ball_predictions: bool,
        close_between_matches: bool = True,
        rlbot_server_ip: str = RLBOT_SERVER_IP,
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        """
        Connects to the RLBot server specifying the given settings.

        - wants_match_communications: Whether match communication messages should be sent to this process.
        - wants_ball_predictions: Whether ball prediction messages should be sent to this process.
        - close_between_matches: Whether RLBot should close this connection between matches, specifically upon
            `StartMatch` and `StopMatch` messages, since RLBot does not actually detect the ending of matches.
        """
        assert not self.is_connected, "Connection has already been established"

        self.socket.settimeout(self.connection_timeout)
        try:
            begin_time = time.time()
            next_warning = 10
            while time.time() < begin_time + self.connection_timeout:
                try:
                    self.socket.connect((rlbot_server_ip, rlbot_server_port))
                    self.is_connected = True
                    break
                except ConnectionRefusedError:
                    time.sleep(0.1)
                except ConnectionAbortedError:
                    time.sleep(0.1)
                if time.time() > begin_time + next_warning:
                    next_warning *= 2
                    self.logger.warning(
                        "Connection is being refused/aborted on %s:%s. Trying again ...",
                        rlbot_server_ip,
                        rlbot_server_port,
                    )
            if not self.is_connected:
                raise ConnectionRefusedError(
                    "Connection was refused/aborted repeatedly! "
                    "Ensure that Rocket League and the RLBotServer is running. "
                    "Try calling `ensure_server_started()` before connecting."
                )
        except TimeoutError as e:
            raise TimeoutError(
                "Took too long to connect to the RLBot! "
                "Ensure that Rocket League and the RLBotServer is running."
                "Try calling `ensure_server_started()` before connecting."
            ) from e
        finally:
            self.socket.settimeout(None)

        self.logger.info(
            "SocketRelay connected to port %s from port %s!",
            rlbot_server_port,
            self.socket.getsockname()[1],
        )

        for handler in self.on_connect_handlers:
            handler()

        self.send_msg(
            flat.ConnectionSettings(
                agent_id=self.agent_id,
                wants_ball_predictions=wants_ball_predictions,
                wants_comms=wants_match_communications,
                close_between_matches=close_between_matches,
            )
        )

    def run(self, *, background_thread: bool = False):
        """
        Handle incoming messages until disconnected.
        If `background_thread` is `True`, a background thread will be started for this.
        """
        assert self.is_connected, "Connection has not been established"
        assert not self._running, "Message handling is already running"
        if background_thread:
            Thread(target=self.run).start()
        else:
            self._running = True
            while self._running and self.is_connected:
                self._running = (
                    self.handle_incoming_messages(blocking=True)
                    != MsgHandlingResult.TERMINATED
                )
            self._running = False

    def handle_incoming_messages(self, blocking: bool = False) -> MsgHandlingResult:
        """
        Empties queue of incoming messages (should be called regularly, see `run`).
        Optionally blocking, ensuring that at least one message will be handled.

        First boolean returns true message handling should continue running, and
        false if RLBotServer has asked us to shut down or an error happened.

        Second boolean returns true if there might be more messages to handle without a delay.
        """
        assert self.is_connected, "Connection has not been established"
        try:
            self.socket.setblocking(blocking)
            incoming_message = self.read_message()
        except BlockingIOError:
            # No incoming messages and blocking==False
            return MsgHandlingResult.NO_INCOMING_MSGS
        except:
            self.logger.error("SocketRelay disconnected unexpectedly!")
            return MsgHandlingResult.TERMINATED

        try:
            return self.handle_incoming_message(incoming_message)
        except flat.InvalidFlatbuffer as e:
            self.logger.error(
                "Error while unpacking message (%s bytes): %s",
                len(incoming_message),
                e,
            )
            return MsgHandlingResult.TERMINATED
        except Exception as e:
            self.logger.error(
                "Unexpected error while handling message of type: %s",
                e,
            )
            return MsgHandlingResult.TERMINATED

    def handle_incoming_message(self, incoming_message: bytes) -> MsgHandlingResult:
        """
        Handles a messages by passing it to the relevant handlers.
        Returns True if the message was NOT a shutdown request
        """

        flatbuffer = flat.CorePacket.unpack(incoming_message).message

        for raw_handler in self.raw_handlers:
            raw_handler(flatbuffer)

        match flatbuffer.item:
            case flat.DisconnectSignal():
                return MsgHandlingResult.TERMINATED
            case flat.GamePacket() as packet:
                for handler in self.packet_handlers:
                    handler(packet)
            case flat.FieldInfo() as field_info:
                for handler in self.field_info_handlers:
                    handler(field_info)
            case flat.MatchConfiguration() as match_config:
                for handler in self.match_config_handlers:
                    handler(match_config)
            case flat.MatchComm() as match_comm:
                for handler in self.match_comm_handlers:
                    handler(match_comm)
            case flat.BallPrediction() as ball_prediction:
                for handler in self.ball_prediction_handlers:
                    handler(ball_prediction)
            case flat.ControllableTeamInfo() as controllable_team_info:
                for handler in self.controllable_team_info_handlers:
                    handler(controllable_team_info)
            case flat.RenderingStatus() as rendering_status:
                for handler in self.rendering_status_handlers:
                    handler(rendering_status)
            case _:
                self.logger.warning(
                    "Received unknown message type: %s",
                    type(flatbuffer.item).__name__,
                )

        return MsgHandlingResult.MORE_MSGS_QUEUED

    def disconnect(self):
        if not self.is_connected:
            self.logger.warning("Asked to disconnect but was already disconnected.")
            return

        self.send_msg(flat.DisconnectSignal())
        timeout = 5.0
        while self._running and timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
        if timeout <= 0:
            self.logger.critical("RLBot is not responding to our disconnect request!?")
            self._running = False

        assert (
            not self._running
        ), "Disconnect request or timeout should have set self._running to False"
        self.is_connected = False
