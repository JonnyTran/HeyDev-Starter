"use client";

import { Geist, Geist_Mono } from "next/font/google";
import { CopilotKit } from "@copilotkit/react-core";
import "./globals.css";
import "@copilotkit/react-ui/styles.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <title>DevRel Publisher</title>
        <meta name="description" content="Agentic DevRel content publisher for GitHub repositories" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <CopilotKit
          agent="devrel_publisher"
          runtimeUrl="http://localhost:8000/copilotkit"
        >
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
