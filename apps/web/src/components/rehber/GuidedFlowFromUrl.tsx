"use client";

import { useSearchParams } from "next/navigation";
import { GuidedFlow } from "./GuidedFlow";

/** Bağlantıdaki `?islem=` değerine göre rehberi başlatır; değer değişince rehber baştan açılır. */
export function GuidedFlowFromUrl() {
  const islem = useSearchParams().get("islem") ?? undefined;
  return <GuidedFlow key={islem ?? ""} initialProcess={islem} />;
}
