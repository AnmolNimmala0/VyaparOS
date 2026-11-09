import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VyaparOS — Your Business, Simplified",
  description:
    "A voice-first operating system for India's small businesses.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
