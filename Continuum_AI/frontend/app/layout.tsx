import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Continuum AI",
  description: "Evidence-backed, permission-aware knowledge handover.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
