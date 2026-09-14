import SupportCockpit from "@/components/SupportCockpit";
import analysis from "@/data/analysis.json";
import evaluation from "@/data/evaluation-summary.json";

export default function Home() {
  return <SupportCockpit analysis={analysis} evaluation={evaluation} />;
}
