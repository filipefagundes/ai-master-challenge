import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sinal 002 — Inteligência de suporte",
  description: "Diagnóstico operacional e triagem assistida por IA para o Challenge 002 do G4.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
