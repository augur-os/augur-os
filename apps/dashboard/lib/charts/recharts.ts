import dynamic from "next/dynamic";
import type { ComponentType } from "react";

type RechartsModule = typeof import("recharts");

export function dynamicRecharts<Name extends keyof RechartsModule>(
  name: Name,
): ComponentType<any> {
  return dynamic(
    () =>
      import("recharts").then(
        (module) => module[name] as ComponentType<any>,
      ),
    { ssr: false },
  );
}
