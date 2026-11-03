/* eslint-disable react/forbid-dom-props -- ImageResponse rasterizes these styles into PNG bytes; no HTML style is served. */
import { ImageResponse } from "next/og";
import { brand } from "@brand";
export function GET(request: Request) {
  const size = new URL(request.url).searchParams.get("size") === "192" ? 192 : 512;
  return new ImageResponse(
    <div
      style={{
        display: "flex",
        width: "100%",
        height: "100%",
        alignItems: "center",
        justifyContent: "center",
        background: brand.colours.accent,
      }}
    >
      <svg width={size * 0.7} height={size * 0.7} viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="43" fill="none" stroke="white" strokeWidth="6" />
        <path
          d="M50 23 V50 L69 61"
          fill="none"
          stroke="white"
          strokeWidth="6"
          strokeLinecap="round"
        />
      </svg>
    </div>,
    { width: size, height: size },
  );
}
