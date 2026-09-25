import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Astra | Embodied Systems Architecture Workbench",
  description: "Traceable mission, contracts, and safety evidence for the Astra synthetic robot.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
