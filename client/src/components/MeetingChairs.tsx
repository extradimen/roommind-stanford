import { useMemo } from "react";
import {
  CHAIR_FIT_HEIGHT,
  resolveChairPosesFromGraph,
  resolveNegotiationChairs,
} from "../sceneChairs";
import GltfPropModel from "./GltfPropModel";
import type { SeatLayout } from "../sceneLayout";

type Props = {
  chairUrl: string;
  seatLayout: SeatLayout;
  sceneConfig?: Record<string, unknown>;
};

export default function MeetingChairs({ chairUrl, seatLayout, sceneConfig }: Props) {
  const chairs = useMemo(() => {
    const fromGraph = resolveChairPosesFromGraph(sceneConfig);
    if (fromGraph?.length) return fromGraph;
    return resolveNegotiationChairs(seatLayout.seats);
  }, [sceneConfig, seatLayout.seats]);

  return (
    <>
      {chairs.map((chair) => (
        <group
          key={chair.id}
          position={chair.position}
          rotation={[0, chair.rotationY, 0]}
          scale={chair.scale ?? 1}
        >
          <GltfPropModel
            url={chairUrl}
            instanceId={chair.id}
            seated={false}
            manifestScale={1}
            fitHeight={CHAIR_FIT_HEIGHT}
          />
        </group>
      ))}
    </>
  );
}
