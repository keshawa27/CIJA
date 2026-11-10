import type { Metadata } from "next";
import { connection } from "next/server";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Vela client intake",
  description: "Client Intake Journey Automation prototype",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await connection(); // render per request, so each page gets the CSP nonce from proxy.ts
  return (
    <html lang="en-AU" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <p className="bg-amber-200 px-4 py-1 text-center text-xs font-semibold text-amber-950">
          DEMO — synthetic data only. Do not enter real personal information.
        </p>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
