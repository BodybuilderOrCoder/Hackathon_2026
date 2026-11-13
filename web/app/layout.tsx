import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "FleetMix AI | Điều vận logistics", description: "Hệ thống điều vận, lệnh giao hàng, phương tiện và pallet FleetMix AI" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
