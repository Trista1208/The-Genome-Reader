import type { Metadata } from "next";
import localFont from "next/font/local";
import { ConvexClientProvider } from "./ConvexClientProvider";
import "./globals.css";

const switzer = localFont({
  src: "../public/fonts/switzer/TTF/Switzer-Variable.ttf",
  display: "swap",
  variable: "--font-switzer",
});

const panchang = localFont({
  src: "../public/fonts/panchang/TTF/Panchang-Variable.ttf",
  display: "swap",
  variable: "--font-panchang",
});

export const metadata: Metadata = {
  title: "Breakpoint — Antibiotic Response Intelligence",
  description:
    "Research decision support for estimating antibiotic response from an assembled bacterial genome.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${switzer.variable} ${panchang.variable}`}>
      <body>
        <ConvexClientProvider>{children}</ConvexClientProvider>
      </body>
    </html>
  );
}
