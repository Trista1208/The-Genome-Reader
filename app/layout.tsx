import type { Metadata } from "next";
import localFont from "next/font/local";
import { ConvexClientProvider } from "./ConvexClientProvider";
import "./globals.css";

const switzer = localFont({
  src: "../Fonts/TTF/Switzer-Variable.ttf",
  display: "swap",
  variable: "--font-switzer",
});

export const metadata: Metadata = {
  title: "The Genome Reader — Antibiotic Response Intelligence",
  description:
    "Research decision support for estimating antibiotic response from an assembled bacterial genome.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={switzer.variable}>
      <body>
        <ConvexClientProvider>{children}</ConvexClientProvider>
      </body>
    </html>
  );
}
