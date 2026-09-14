import SupportCockpit from "@/components/SupportCockpit";
import analysis from "@/data/analysis.json";

export default function Home() {
  return <SupportCockpit analysis={analysis} />;
}
