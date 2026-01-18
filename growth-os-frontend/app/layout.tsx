import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Growth-OS | Google Ads AI Optimizer",
  description: "Next-generation AI-driven ad management and optimization.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="light">
      <body className={`${inter.className} bg-gray-50 text-slate-900 antialiased`}>
        {children}
      </body>
    </html>
  );
}
