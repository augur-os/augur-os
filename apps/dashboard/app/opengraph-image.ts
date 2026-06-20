import { ImageResponse } from "next/og";
import { createElement } from "react";
import type { CSSProperties, ReactElement } from "react";

const palette = {
  bg: "#09090b",
  bgGradientEnd: "#1e1b4b",
  cyan: "#22d3ee",
  purple: "#a855f7",
  purpleLight: "#c084fc",
  textPrimary: "#ffffff",
  textMuted: "#94a3b8",
};

const containerStyle: CSSProperties = {
  background: `linear-gradient(135deg, ${palette.bg} 0%, ${palette.bgGradientEnd} 100%)`,
  width: "100%",
  height: "100%",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "sans-serif",
};

const iconWrapStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const textWrapStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  marginTop: -20,
};

const titleStyle: CSSProperties = {
  fontSize: 80,
  fontWeight: 800,
  color: palette.textPrimary,
  letterSpacing: "-0.05em",
};

const subtitleStyle: CSSProperties = {
  fontSize: 32,
  color: palette.textMuted,
  marginTop: 10,
  letterSpacing: "0.05em",
  textTransform: "uppercase",
};

export const alt = "Augur - Your Second Brain";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

function renderAugurMark(): ReactElement {
  return createElement(
    "svg",
    {
      width: "300",
      height: "300",
      viewBox: "0 0 100 100",
      fill: "none",
      xmlns: "http://www.w3.org/2000/svg",
    },
    createElement("path", {
      d: "M50 30L67 40V60L50 70L33 60V40L50 30Z",
      stroke: palette.cyan,
      strokeWidth: "2",
      fill: "none",
      strokeLinejoin: "round",
    }),
    createElement("path", {
      d: "M50 30L67 40V60L50 70L33 60V40L50 30Z",
      fill: palette.cyan,
      fillOpacity: "0.1",
    }),
    createElement("circle", { cx: "50", cy: "50", r: "4", fill: palette.purple }),
    createElement("circle", {
      cx: "50",
      cy: "15",
      r: "5",
      stroke: palette.purple,
      strokeWidth: "2",
      fill: palette.bg,
    }),
    createElement("line", {
      x1: "50",
      y1: "21",
      x2: "50",
      y2: "30",
      stroke: palette.purple,
      strokeWidth: "1",
      strokeOpacity: "0.5",
    }),
    createElement("circle", {
      cx: "80",
      cy: "75",
      r: "4",
      stroke: palette.purpleLight,
      strokeWidth: "2",
      fill: palette.bg,
    }),
    createElement("line", {
      x1: "67",
      y1: "60",
      x2: "76",
      y2: "71",
      stroke: palette.purpleLight,
      strokeWidth: "1",
      strokeOpacity: "0.5",
    }),
    createElement("circle", {
      cx: "20",
      cy: "75",
      r: "4",
      stroke: palette.cyan,
      strokeWidth: "2",
      fill: palette.bg,
    }),
    createElement("line", {
      x1: "33",
      y1: "60",
      x2: "24",
      y2: "71",
      stroke: palette.cyan,
      strokeWidth: "1",
      strokeOpacity: "0.5",
    }),
  );
}

export default async function Image() {
  return new ImageResponse(
    createElement(
      "div",
      { style: containerStyle },
      createElement("div", { style: iconWrapStyle }, renderAugurMark()),
      createElement(
        "div",
        { style: textWrapStyle },
        createElement("div", { style: titleStyle }, "Augur"),
        createElement("div", { style: subtitleStyle }, "Your Second Brain"),
      ),
    ),
    size,
  );
}
