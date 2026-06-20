"use client";

import type { LayoutConfigModalProps } from "./LayoutConfigModal.types";
import { useLayoutConfigController } from "./LayoutConfigModal.controller";
import {
  EmbeddedLayoutSettings,
  DialogLayoutSettings,
} from "./LayoutConfigModal.surfaces";

export { useWidgetVisibility, useIsFavorite } from "./LayoutConfigModal.hooks";

export default function LayoutConfigModal(props: LayoutConfigModalProps) {
  const surfaceProps = useLayoutConfigController(props);
  return props.embedded ? (
    <EmbeddedLayoutSettings {...surfaceProps} />
  ) : (
    <DialogLayoutSettings {...surfaceProps} />
  );
}
