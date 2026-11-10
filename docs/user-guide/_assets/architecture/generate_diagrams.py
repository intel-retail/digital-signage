"""Render the three architecture figures (original, +MCP server, +video diffusion) on one shared layout.

Blocks that exist in more than one figure keep the same relative layout. The MCP figures add DX units of
width between the broker and the Web UI so the larger text of the extra MCP blocks fits.
Usage: python generate_diagrams.py   (writes PNGs next to this script)
"""
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from matplotlib.path import Path

W, Y_TOP, Y_BOTTOM = 1960, 85, 740
MCP_DX = 250
FS = 1.25  # font scale applied to all diagram text
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

CLUSTER_FC, CLUSTER_EC = "#f6f7fd", "#d5d8ec"
CHIP_FC, CHIP_TC = "#f1e0fa", "#4a148c"
GREEN, GREEN_DARK = "#1b5e20", "#2e7d32"

STYLES = {
    "input": ("#e3f2fd", "#1e88e5", "#0d47a1"),
    "pid": ("#efebe9", "#6d4c41", "#3e2723"),
    "broker": ("#fff8e1", "#f9a825", "#5d4037"),
    "psl": ("#f3e5f5", "#8e24aa", "#4a148c"),
    "aig": ("#fff3e0", "#fb8c00", "#bf360c"),
    "media": ("#e0f7fa", "#00acc1", "#006064"),
    "nginx": ("#eceff1", "#546e7a", "#263238"),
    "new": (GREEN, GREEN_DARK, "#ffffff"),
}


def cluster(ax, x, y, w, h, title):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=4",
                                fc=CLUSTER_FC, ec=CLUSTER_EC, lw=1, zorder=1))
    ax.text(x + w / 2, y + 14, title, ha="center", va="center", fontsize=8 * FS, color="#37474f", zorder=2)


def box(ax, x, y, w, h, text, style, lw=1.6, bold_first=False, pill=False, bold_lines=()):
    fc, ec, tc = STYLES[style]
    rounding = h / 2 if pill else 3
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rounding}",
                                fc=fc, ec=ec, lw=lw, zorder=3))
    label(ax, x + w / 2, y + h / 2, text, tc, bold_first, bold_lines)


def label(ax, cx, cy, text, color, bold_first=False, bold_lines=()):
    lines = text.split("\n")
    line_h = 12.5 * FS
    top = cy - line_h * (len(lines) - 1) / 2
    for i, line in enumerate(lines):
        bold = (bold_first and i == 0) or line in bold_lines
        ax.text(cx, top + i * line_h, line, ha="center", va="center", fontsize=7.8 * FS, color=color,
                fontweight="bold" if bold else "normal", zorder=5)


def cylinder(ax, x, y, w, h, text, style, lw=1.6):
    fc, ec, tc = STYLES[style]
    ry = 9
    ax.add_patch(Ellipse((x + w / 2, y + h - ry), w, 2 * ry, fc=fc, ec=ec, lw=lw, zorder=3))
    ax.add_patch(Rectangle((x, y + ry), w, h - 2 * ry, fc=fc, ec="none", zorder=3))
    ax.plot([x, x], [y + ry, y + h - ry], color=ec, lw=lw, zorder=4)
    ax.plot([x + w, x + w], [y + ry, y + h - ry], color=ec, lw=lw, zorder=4)
    ax.add_patch(Ellipse((x + w / 2, y + ry), w, 2 * ry, fc=fc, ec=ec, lw=lw, zorder=4))
    label(ax, x + w / 2, y + h / 2 + 8, text, tc)


def parallelogram(ax, x, y, w, h, text, style, lw=1.6, skew=12):
    fc, ec, tc = STYLES[style]
    ax.add_patch(Polygon([(x + skew, y), (x + w, y), (x + w - skew, y + h), (x, y + h)],
                         closed=True, fc=fc, ec=ec, lw=lw, zorder=3))
    label(ax, x + w / 2, y + h / 2, text, tc)


def hexagon(ax, x, y, w, h, text, style, lw=1.6):
    fc, ec, tc = STYLES[style]
    k = 14
    ax.add_patch(Polygon([(x + k, y), (x + w - k, y), (x + w, y + h / 2), (x + w - k, y + h),
                          (x + k, y + h), (x, y + h / 2)], closed=True, fc=fc, ec=ec, lw=lw, zorder=3))
    label(ax, x + w / 2, y + h / 2, text, tc)


def _rounded(points, r=10):
    verts, codes = [points[0]], [Path.MOVETO]
    for i in range(1, len(points) - 1):
        p0, p1, p2 = points[i - 1], points[i], points[i + 1]
        d0, d1 = math.dist(p0, p1), math.dist(p1, p2)
        rr = min(r, d0 / 2, d1 / 2)
        a = (p1[0] + (p0[0] - p1[0]) / d0 * rr, p1[1] + (p0[1] - p1[1]) / d0 * rr)
        b = (p1[0] + (p2[0] - p1[0]) / d1 * rr, p1[1] + (p2[1] - p1[1]) / d1 * rr)
        verts += [a, p1, b]
        codes += [Path.LINETO, Path.CURVE3, Path.CURVE3]
    verts.append(points[-1])
    codes.append(Path.LINETO)
    return Path(verts, codes)


def edge(ax, points, color="#222222", lw=1.2, dotted=False, arrow=True, chip=None, chip_at=None):
    patch = FancyArrowPatch(path=_rounded(points), arrowstyle="-|>,head_length=4.5,head_width=2.4" if arrow else "-",
                            mutation_scale=1.3, color=color, lw=lw, shrinkA=0, shrinkB=0,
                            linestyle=(0, (3, 2.5)) if dotted else "-", zorder=2.5)
    ax.add_patch(patch)
    if chip:
        ax.text(chip_at[0], chip_at[1], chip, ha="center", va="center", fontsize=7.4 * FS, color=CHIP_TC, zorder=6,
                linespacing=1.15, bbox=dict(boxstyle="round,pad=0.22", fc=CHIP_FC, ec="none"))


def render(variant, filename):
    mcp = variant >= 2
    video = variant >= 3
    dx = MCP_DX if mcp else 0
    width = W + dx + 50 if mcp else W
    # Highlight color goes to whatever is new in this figure only.
    mcp_style = "new" if variant == 2 else "psl"
    mcp_edge = GREEN if variant == 2 else "#222222"
    mcp_lw = 1.8 if variant == 2 else 1.2

    fig = plt.figure(figsize=(width / 100, (Y_BOTTOM - Y_TOP) / 100), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(Y_BOTTOM, Y_TOP)
    ax.axis("off")

    # --- shared blocks ---
    cluster(ax, 15, 350, 200, 100, "Input")
    box(ax, 30, 375, 170, 50, "RTSP Camera /\nSimulation Video", "input")

    cluster(ax, 230, 190, 260, 290, "PID \u2014 dlstreamer-pipeline-server")
    box(ax, 252, 375, 216, 50, "DL Streamer Pipeline Server\nYOLO11s detection", "pid")

    cluster(ax, 520, 190, 180, 110, "Broker")
    box(ax, 535, 230, 150, 50, "mqtt-broker\nEclipse Mosquitto", "broker")

    if mcp:
        top = 95 if video else 190
        cluster(ax, 715, top, 1100 + dx - 715, 590 - top, "Web UI container \u2014 Flask + built-in MCP server")
    else:
        cluster(ax, 860, 190, 240, 110, "Web UI \u2014 Flask")
    box(ax, 875 + dx, 230, 210, 50, "Product selection logic\nProductAssociations.csv", "psl")

    cluster(ax, 1300 + dx, 110, 535, 330 if video else 200, "AIG-server container")
    box(ax, 1320 + dx, 150, 240, 50, "ASe \u2014 Advertise Searcher\n/ase/predef/query/ad", "aig")
    cylinder(ax, 1695 + dx, 143, 125, 64, "Database", "aig")
    box(ax, 1320 + dx, 230, 240, 50, "AIG \u2014 Model Inference\n/aig/minf/ SDXL-Turbo", "aig")

    box(ax, 1470 + dx, 500, 200, 70, "nginx\nTLS reverse proxy :5000", "nginx")
    box(ax, 1790 + dx, 503, 130, 24, "Browser Client", "nginx", pill=True)

    cluster(ax, 1300 + dx, 620, 480, 100, "Media")
    box(ax, 1320 + dx, 645, 190, 50, "mediamtx\nWebRTC/RTSP relay", "media")
    box(ax, 1550 + dx, 645, 150, 50, "coturn\nTURN server", "media")

    # --- shared edges ---
    qx = 1200 + dx
    pex = 1320 if mcp else 1024  # x where the Product -> nginx edge leaves the product box
    edge(ax, [(200, 400), (252, 400)])
    edge(ax, [(360, 375), (360, 255), (535, 255)], chip="detections", chip_at=(450, 255))
    edge(ax, [(685, 255), (875 + dx, 255)], chip="labels", chip_at=(800 if mcp else 780, 255))
    edge(ax, [(1085 + dx, 240), (qx, 240), (qx, 175), (1320 + dx, 175)], chip="query predefined ad", chip_at=(qx, 208))
    edge(ax, [(1560 + dx, 175), (1695 + dx, 175)], chip="vector search", chip_at=(1627 + dx, 175))
    edge(ax, [(1085 + dx, 255), (1320 + dx, 255)], chip="fallback: generate ad", chip_at=(1170 + dx, 255))
    edge(ax, [(1560 + dx, 255), (1620 + dx, 255), (1620 + dx, 500)])
    edge(ax, [(pex, 280), (pex, 445), (1500 + dx, 445), (1500 + dx, 500)])
    edge(ax, [(360, 425), (360, 670), (1320 + dx, 670)], chip="video via WebRTC", chip_at=(800, 670))
    edge(ax, [(1510 + dx, 670), (1550 + dx, 670)], arrow=False)
    edge(ax, [(1490 + dx, 645), (1490 + dx, 570)])
    edge(ax, [(1620 + dx, 645), (1620 + dx, 570)])
    edge(ax, [(1670 + dx, 515), (1790 + dx, 515)])

    # --- MCP additions ---
    if mcp:
        cylinder(ax, 740, 300, 170, 104, "context_rules.json\nweather/demand/\nage_mix/daypart\n-> product", mcp_style)
        parallelogram(ax, 740, 416, 200, 112,
                      "Role: lets an LLM/\nagent READ signage\nstate and ACT on it,\nby calling the SAME\nfunctions the\ncamera flow uses", mcp_style)
        tool_names = ["describe", "get_current_ad", "get_catalog", "select_dynamic_ad", "trigger_ad"]
        if video:
            tool_names.append("trigger_video_ad")
        tool_names.append("clear_ad")
        tools = "\n".join(tool_names)
        box(ax, 1040, 342, 230, 196,
            "MCP server :5100\nROLE: agent control surface\nStreamable HTTP, no new\nbusiness logic\n" + tools,
            mcp_style, bold_first=True, bold_lines=("trigger_video_ad",))

        edge(ax, [(910, 352), (1040, 352)], color=mcp_edge, dotted=True, lw=1.4)
        edge(ax, [(940, 472), (1040, 472)], color=mcp_edge, dotted=True, lw=1.4)
        edge(ax, [(1155, 342), (1155, 280)], color=mcp_edge, lw=mcp_lw,
             chip="direct function calls,\nsame process/\nshared state", chip_at=(1155, 311))
        edge(ax, [(1155, 538), (1155, 558), (1470 + dx, 558)], color=mcp_edge, lw=mcp_lw)

        hexagon(ax, 1790 + dx, 545, 190, 34, "LLM / Agent client", "new" if variant == 2 else "nginx")
        edge(ax, [(1670 + dx, 548), (1790 + dx, 548)], color=mcp_edge, lw=mcp_lw,
             chip="/mcp", chip_at=(1730 + dx, 548))
        edge(ax, [(1790 + dx, 568), (1670 + dx, 568)], color=mcp_edge, dotted=True, lw=1.4,
             chip="context, e.g. weather=rain", chip_at=(1745 + dx, 596))

    # --- video diffusion additions ---
    if video:
        box(ax, 1320 + dx, 345, 240, 70, "AIG \u2014 Video Inference\n/aig/mvid/ LTX-Video\nText2VideoPipeline", "new")
        edge(ax, [(1085 + dx, 275), (1195 + dx, 275), (1195 + dx, 380), (1320 + dx, 380)], color=GREEN, lw=1.8,
             chip="fallback: generate\nvideo ad (MCP-only)", chip_at=(1195 + dx, 327))
        edge(ax, [(1560 + dx, 380), (1590 + dx, 380), (1590 + dx, 500)], color=GREEN, lw=1.8)
        parallelogram(ax, 1130, 125, 200, 85,
                      "pre_defined_ad_video\n(CSV column): local\nfile lookup, no\nChromaDB/AIG call", "new")
        edge(ax, [(1230, 210), (1230, 230)], color=GREEN, dotted=True, lw=1.6)

    fig.savefig(os.path.join(OUT_DIR, filename), facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    render(1, "architecture_1_original.png")
    render(2, "architecture_2_mcp.png")
    render(3, "architecture_3_mcp_video.png")
