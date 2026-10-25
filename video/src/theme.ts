import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const { fontFamily: sans } = loadInter("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] });
export const { fontFamily: mono } = loadMono("normal", { weights: ["400", "500"], subsets: ["latin"] });

export const FPS = 30;
export const W = 1920;
export const H = 1080;

/** Same tokens as the web app, so the video and the product look like one thing. */
export const c = {
  ink: "#191918",
  ink2: "#66655f",
  paper: "#ffffff",
  side: "#f8f8f7",
  rule: "#ebebe8",
  night: "#0d0d0f",
  nightRule: "rgba(255,255,255,0.10)",
  glass: "rgba(18,18,20,0.62)",
  glassBorder: "rgba(255,255,255,0.16)",
  amber: "#f0b25e",
  rose: "#ff6d8c",
  blue: "#7fa8ff",
  green: "#5fd29b",
  violet: "#8f80ff",
  ai: "linear-gradient(135deg, #f2b33d 0%, #e8466c 48%, #6c5cf0 100%)",
};

export const ease = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);
