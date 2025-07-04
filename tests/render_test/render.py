from email.policy import default

from rlbot import flat
from rlbot.flat import BallAnchor, CarAnchor, Color, RenderAnchor, Vector3
from rlbot.managers import Script


class RenderFun(Script):
    needs_render = True
    last_state = flat.MatchPhase.Inactive
    player_count = 0

    def initialize(self):
        self.update_rendering_status(True)

    def handle_packet(self, packet: flat.GamePacket):
        if (
            packet.match_info.match_phase != flat.MatchPhase.Replay
            and self.last_state == flat.MatchPhase.Replay
        ) or len(packet.players) != self.player_count:
            self.needs_render = True
        self.last_state = packet.match_info.match_phase

        if self.needs_render:
            self.needs_render = False
            self.player_count = len(packet.players)

            radius = 0
            if len(packet.balls) > 0:
                match packet.balls[0].shape.item:
                    case flat.SphereShape() | flat.CylinderShape() as shape:
                        radius = shape.diameter / 2
                    case flat.BoxShape() as shape:
                        radius = shape.length / 2

            self.do_render(radius)

        with self.renderer.context("tick", self.renderer.red):
            self.renderer.set_resolution(1920, 1080)
            hsv = self.renderer.create_color_hsv(
                packet.match_info.seconds_elapsed * 0.1, 1.0, 1.0
            )
            self.renderer.draw_string_2d("HSV 300px 50px", 300, 50, 1.0, hsv)
            self.renderer.draw_string_2d(
                "Red 330px 70px", 330, 70, 1.0
            )  # Use default color
            self.renderer.set_resolution(1, 1)

    def do_render(self, radius: float):
        self.renderer.begin_rendering()

        points = [
            BallAnchor(local=Vector3(radius, radius, radius)),
            BallAnchor(local=Vector3(radius, radius, -radius)),
            BallAnchor(local=Vector3(radius, -radius, -radius)),
            BallAnchor(local=Vector3(radius, -radius, radius)),
            BallAnchor(local=Vector3(-radius, -radius, radius)),
            BallAnchor(local=Vector3(-radius, -radius, -radius)),
            BallAnchor(local=Vector3(-radius, radius, -radius)),
            BallAnchor(local=Vector3(-radius, radius, radius)),
            BallAnchor(local=Vector3(radius, radius, radius)),
        ]

        for i in range(1, len(points)):
            self.renderer.draw_line_3d(points[i - 1], points[i], self.renderer.yellow)

        points = [
            BallAnchor(),
            CarAnchor(0),
            Vector3(),
        ]

        for i in range(1, len(points)):
            self.renderer.draw_line_3d(points[i - 1], points[i], self.renderer.red)

        self.renderer.draw_rect_3d(
            RenderAnchor(Vector3(0, 0, 100), CarAnchor(0, Vector3(200, 0, 0))),
            0.02,
            0.02,
            self.renderer.blue,
        )
        self.renderer.draw_rect_3d(
            CarAnchor(0, Vector3(200, 0, 0)), 0.02, 0.02, self.renderer.blue
        )

        self.renderer.draw_rect_2d(0.75, 0.75, 0.1, 0.1, Color(150, 30, 100))
        self.renderer.draw_rect_2d(0.75, 0.75, 0.1, 0.1, self.renderer.black)
        for hkey, h in {
            "left": flat.TextHAlign.Left,
            "center": flat.TextHAlign.Center,
            "right": flat.TextHAlign.Right,
        }.items():
            for vkey, v in {
                "top": flat.TextVAlign.Top,
                "center": flat.TextVAlign.Center,
                "bottom": flat.TextVAlign.Bottom,
            }.items():
                self.renderer.draw_string_2d(
                    f"\n\n{vkey:^14}\n{hkey:^14}\n\n",
                    0.75,
                    0.75,
                    0.66,
                    self.renderer.white,
                    h_align=h,
                    v_align=v,
                )

        self.renderer.end_rendering()


if __name__ == "__main__":
    RenderFun("testing/render_test").run(
        wants_match_communications=False, wants_ball_predictions=False
    )
