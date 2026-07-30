import Link from "next/link";

import { PortfolioPanel } from "./portfolio-panel";

export default function QecPortfolioPage() {
  return (
    <main>
      <p><Link href="/">← Problem Console</Link></p>
      <header>
        <p>Local advisory workspace</p>
        <h1>QEC Problem Portfolio</h1>
        <p>Compare approved quantum error-correction problems using completed local assessments and frozen external evidence.</p>
      </header>
      <PortfolioPanel />
    </main>
  );
}
