import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClinicPass",
  description: "Prepare administrative healthcare documents before arrival.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link className="brand" href="/"><span className="brandMark">C</span> ClinicPass</Link>
          <nav aria-label="Primary navigation">
            <Link href="/patient/start">Patient</Link>
            <Link href="/clinic">Clinic team</Link>
          </nav>
        </header>
        {children}
        <footer>
          <strong>Demo with synthetic data only.</strong> Administrative readiness is not a coverage guarantee. Identity, e-card, and original documents are checked on site.
        </footer>
      </body>
    </html>
  );
}

