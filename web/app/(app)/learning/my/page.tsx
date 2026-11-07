import type { Metadata } from "next";

import { MyLearning } from "@/components/learning/my-learning";

export const metadata: Metadata = { title: "My learning" };

export default function Page() {
  return <MyLearning />;
}
