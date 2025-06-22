import math
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from typing import Optional

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.utils.logging import get_logger

MAX_INT = 2147483647 // 2
DEFAULT_GROUP_ID = "default"


def _get_anchor(
    anchor: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
):
    """
    Convert any of the render anchor types to a RenderAnchor.
    """
    match anchor:
        case flat.BallAnchor() | flat.CarAnchor():
            return flat.RenderAnchor(relative=anchor)
        case flat.Vector3():
            return flat.RenderAnchor(anchor)
        case _:
            return anchor


class Renderer:
    """
    An interface to the debug rendering features.
    """

    transparent = flat.Color(a=0)
    black = flat.Color()
    white = flat.Color(255, 255, 255)
    grey = gray = flat.Color(128, 128, 128)
    blue = flat.Color(0, 0, 255)
    red = flat.Color(255, 0, 0)
    green = flat.Color(0, 128, 0)
    lime = flat.Color(0, 255, 0)
    yellow = flat.Color(255, 255, 0)
    orange = flat.Color(225, 128, 0)
    cyan = flat.Color(0, 255, 255)
    pink = flat.Color(255, 0, 255)
    purple = flat.Color(128, 0, 128)
    teal = flat.Color(0, 128, 128)

    _logger = get_logger("renderer")

    _used_group_ids: set[int] = set()
    _group_id: Optional[int] = None
    _current_renders: list[flat.RenderMessage] = []

    _default_color = white

    _screen_width_factor = 1.0
    _screen_height_factor = 1.0

    def __init__(self, game_interface: SocketRelay):
        self._send_msg: Callable[[flat.RenderGroup | flat.RemoveRenderGroup], None] = (
            game_interface.send_msg
        )

    def set_resolution(self, screen_width: float, screen_height: float):
        """
        By default, the renderer uses screen-space coordinates for 2d, e.g. 0.1 is 10% of screen width.
        Use this function to declare the screen's size in pixels, if you prefer working in pixel coordinates.
        After setting this, `draw_string_2d('Hi', 100, 200, ...)` will draw 'Hi' at pixel coordinates (100, 200).
        """
        self._screen_width_factor = 1.0 / screen_width
        self._screen_height_factor = 1.0 / screen_height

    def set_default_color(self, color: flat.Color):
        """
        Set which color to use when no other color is provided.
        """
        self._default_color = color

    @staticmethod
    def create_color(red: int, green: int, blue: int, alpha: int = 255) -> flat.Color:
        return flat.Color(red, green, blue, alpha)

    @staticmethod
    def create_color_hsv(hue: float, saturation: float, value: float) -> flat.Color:
        i = math.floor(hue * 6)
        f = hue * 6 - i
        p = value * (1 - saturation)
        q = value * (1 - f * saturation)
        t = value * (1 - (1 - f) * saturation)

        match i % 6:
            case 0:
                r, g, b = value, t, p
            case 1:
                r, g, b = q, value, p
            case 2:
                r, g, b = p, value, t
            case 3:
                r, g, b = p, q, value
            case 4:
                r, g, b = t, p, value
            case 5:
                r, g, b = value, p, q

        return flat.Color(math.floor(r * 255), math.floor(g * 255), math.floor(b * 255))

    @staticmethod
    def team_color(team: int, alt_color: bool = False) -> flat.Color:
        """
        Returns the color of the given team (blue or orange),
        or a secondary color (cyan or red) if `alt_color` is True.
        """
        if team == 0:
            return Renderer.cyan if alt_color else Renderer.blue
        elif team == 1:
            return Renderer.red if alt_color else Renderer.orange

        return Renderer.gray if alt_color else Renderer.white

    @staticmethod
    def _get_group_id(group_id: str) -> int:
        return hash(str(group_id).encode("utf-8")) % MAX_INT

    @contextmanager
    def context(self, group_id: str=DEFAULT_GROUP_ID, default_color=None):
        """
        Starts rendering as a context usable in with-statements.
        After the with-statement the rendering is automatically ended.
        Note, the is not possible to have two nested renderings started.

        Example:

        ```
        with renderer.context(default_color=renderer.red):
            renderer.draw_line_3d(car.pos, ball.pos)
            renderer.draw_line_3d(car.pos, goal.pos)
            renderer.draw_line_3d(ball.pos, goal.pos)
        ```
        """
        try:
            self.begin_rendering(group_id)
            if default_color:
                self.set_default_color(default_color)
            yield
        finally:
            self.end_rendering()

    def begin_rendering(self, group_id: str = DEFAULT_GROUP_ID):
        """
        Begins a new render group. All render messages added after this call will be part of this group.
        """
        if self.is_rendering() and len(self._current_renders) > 0:
            self._logger.error(
                "begin_rendering was called twice without end_rendering."
            )
            return

        self._current_renders.clear()
        self._group_id = Renderer._get_group_id(group_id)
        self._used_group_ids.add(self._group_id)

    def end_rendering(self):
        """
        End the current render group and send it to the rlbot server.
        `begin_rendering` must be called before this is called, and the render group will contain
        all render messages queued between these two calls.
        """
        if self._group_id is None:
            if len(self._current_renders) > 0:
                self._logger.error(
                    "`end_rendering` was called without a call to `begin_rendering` first."
                )
            return

        self._send_msg(flat.RenderGroup(self._current_renders, self._group_id))
        self._current_renders.clear()
        self._group_id = None

    def clear_render_group(self, group_id: str = DEFAULT_GROUP_ID):
        """
        Clears all rendering of the provided group.
        Note: It is not possible to clear render groups of other bots.
        """
        group_id_hash = Renderer._get_group_id(group_id)
        self._send_msg(flat.RemoveRenderGroup(group_id_hash))
        self._used_group_ids.discard(group_id_hash)

    def clear_all_render_groups(self):
        """
        Clears all rendering.
        Note: This does not clear render groups created by other bots.
        """
        for group_id in self._used_group_ids:
            self._send_msg(flat.RemoveRenderGroup(group_id))
        self._used_group_ids.clear()

    def is_rendering(self):
        """
        Returns True if `begin_rendering` has been called without a corresponding call to `end_rendering`.
        """
        return self._group_id is not None

    def draw(
        self,
        render: (
            flat.String2D
            | flat.String3D
            | flat.Line3D
            | flat.PolyLine3D
            | flat.Rect2D
            | flat.Rect3D
        ),
    ):
        if not self.is_rendering():
            self._logger.error(
                "Attempted to draw without a render group."
                "Please call `begin_rendering` first, and then `end_rendering` after."
            )
            return

        self._current_renders.append(flat.RenderMessage(render))

    def draw_line_3d(
        self,
        start: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        end: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        color: flat.Color | None = None,
    ):
        """
        Draws a line between two anchors in 3d space.
        """
        self.draw(flat.Line3D(_get_anchor(start), _get_anchor(end), color or self._default_color))

    def draw_polyline_3d(
        self,
        points: Sequence[flat.Vector3],
        color: flat.Color | None = None,
    ):
        """
        Draws a line going through each of the provided points.
        """
        self.draw(flat.PolyLine3D(points, color or self._default_color))

    def draw_string_3d(
        self,
        text: str,
        anchor: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        scale: float,
        foreground: flat.Color | None = None,
        background: flat.Color = flat.Color(a=0),
        h_align: flat.TextHAlign = flat.TextHAlign.Left,
        v_align: flat.TextVAlign = flat.TextVAlign.Top,
    ):
        """
        Draws text anchored in 3d space.
        Characters of the font are 20 pixels tall and 10 pixels wide when `scale == 1.0`.
        """
        self.draw(
            flat.String3D(
                text,
                _get_anchor(anchor),
                scale,
                foreground or self._default_color,
                background,
                h_align,
                v_align,
            )
        )

    def draw_string_2d(
        self,
        text: str,
        x: float,
        y: float,
        scale: float,
        foreground: flat.Color | None = None,
        background: flat.Color = flat.Color(a=0),
        h_align: flat.TextHAlign = flat.TextHAlign.Left,
        v_align: flat.TextVAlign = flat.TextVAlign.Top,
    ):
        """
        Draws text in 2d space.
        X and y uses screen-space coordinates, i.e. 0.1 is 10% of the screen width/height.
        Use `set_resolution` to change to pixel coordinates.
        Characters of the font are 20 pixels tall and 10 pixels wide when `scale == 1.0`.
        """
        self.draw(
            flat.String2D(
                text,
                x * self._screen_width_factor,
                y * self._screen_height_factor,
                scale,
                foreground or self._default_color,
                background,
                h_align,
                v_align,
            )
        )

    def draw_rect_2d(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        color: flat.Color | None = None,
        h_align: flat.TextHAlign = flat.TextHAlign.Left,
        v_align: flat.TextVAlign = flat.TextVAlign.Top,
    ):
        """
        Draws a rectangle anchored in 2d space.
        X, y, width, and height uses screen-space coordinates, i.e. 0.1 is 10% of the screen width/height.
        Use `set_resolution` to change to pixel coordinates.
        """

        self.draw(
            flat.Rect2D(
                x * self._screen_width_factor,
                y * self._screen_height_factor,
                width * self._screen_width_factor,
                height * self._screen_height_factor,
                color or self._default_color,
                h_align,
                v_align,
            )
        )

    def draw_rect_3d(
        self,
        anchor: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        width: float,
        height: float,
        color: flat.Color | None = None,
        h_align: flat.TextHAlign = flat.TextHAlign.Left,
        v_align: flat.TextVAlign = flat.TextVAlign.Top,
    ):
        """
        Draws a rectangle anchored in 3d space.
        Width and height are screen-space sizes, i.e. 0.1 is 10% of the screen width/height.
        Use `set_resolution` to change to pixel coordinates.
        The size does not change based on distance to the camera.
        """
        self.draw(
            flat.Rect3D(
                _get_anchor(anchor),
                width * self._screen_width_factor,
                height * self._screen_height_factor,
                color or self._default_color,
                h_align,
                v_align,
            )
        )
