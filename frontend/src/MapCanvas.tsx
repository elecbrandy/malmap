import Konva from "konva";
import { useEffect, useRef, useState } from "react";
import { Circle, Group, Layer, Stage, Text } from "react-konva";

import type { ScoredEntry } from "./api/client";
import { getTileColor } from "./mapColors";
import { formatScaledSimilarity } from "./similarity";
import "./MapCanvas.css";

const WORLD_SCALE = 240;
const MINIMUM_ZOOM = 0.35;
const MAXIMUM_ZOOM = 2.4;

export type CameraTarget = {
  entry: ScoredEntry;
  requestId: number;
};

type MapCanvasProps = {
  entries: ScoredEntry[];
  cameraTarget: CameraTarget | null;
};

export default function MapCanvas({ entries, cameraTarget }: MapCanvasProps) {
  const containerReference = useRef<HTMLDivElement>(null);
  const stageReference = useRef<Konva.Stage>(null);
  const hasCenteredStage = useRef(false);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 420 });
  const [moveInstantly, setMoveInstantly] = useState(false);

  useEffect(() => {
    const container = containerReference.current;
    if (!container) return;

    const updateWidth = () => {
      setCanvasSize((currentSize) => ({ ...currentSize, width: container.clientWidth }));
    };
    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const stage = stageReference.current;
    if (!stage || canvasSize.width === 0 || hasCenteredStage.current) return;

    stage.position({ x: canvasSize.width / 2, y: canvasSize.height / 2 });
    hasCenteredStage.current = true;
  }, [canvasSize]);

  useEffect(() => {
    const stage = stageReference.current;
    const entry = cameraTarget?.entry;
    if (!stage || !entry || entry.map_x === null || entry.map_y === null) return;

    const scale = Math.max(stage.scaleX(), 0.9);
    const position = {
      x: canvasSize.width / 2 - entry.map_x * WORLD_SCALE * scale,
      y: canvasSize.height / 2 + entry.map_y * WORLD_SCALE * scale,
    };

    if (moveInstantly) {
      stage.scale({ x: scale, y: scale });
      stage.position(position);
      stage.batchDraw();
      return;
    }

    stage.to({
      ...position,
      scaleX: scale,
      scaleY: scale,
      duration: 0.65,
      easing: Konva.Easings.EaseInOut,
    });
  }, [cameraTarget, canvasSize, moveInstantly]);

  function handleWheel(event: Konva.KonvaEventObject<WheelEvent>) {
    event.evt.preventDefault();
    const stage = stageReference.current;
    const pointer = stage?.getPointerPosition();
    if (!stage || !pointer) return;

    const oldScale = stage.scaleX();
    const direction = event.evt.deltaY > 0 ? -1 : 1;
    const newScale = Math.min(
      MAXIMUM_ZOOM,
      Math.max(MINIMUM_ZOOM, direction > 0 ? oldScale * 1.12 : oldScale / 1.12),
    );
    const pointerInWorld = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };

    stage.scale({ x: newScale, y: newScale });
    stage.position({
      x: pointer.x - pointerInWorld.x * newScale,
      y: pointer.y - pointerInWorld.y * newScale,
    });
    stage.batchDraw();
  }

  return (
    <div className="map-panel">
      <div className="map-toolbar">
        <span>드래그로 이동 · 휠로 확대</span>
        <label>
          <input
            type="checkbox"
            checked={moveInstantly}
            onChange={(event) => setMoveInstantly(event.target.checked)}
          />
          즉시 이동
        </label>
      </div>
      <div className="map-viewport" ref={containerReference}>
        {entries.length === 0 && (
          <p className="map-empty">지도에 있는 단어를 찾으면 이곳에 나타납니다.</p>
        )}
        <Stage
          ref={stageReference}
          width={canvasSize.width}
          height={canvasSize.height}
          draggable
          onWheel={handleWheel}
        >
          <Layer>
            {entries.map((entry) => {
              if (entry.map_x === null || entry.map_y === null) return null;
              const entryKey = `${entry.word}-${entry.sense_no}`;
              const isHighlighted =
                cameraTarget?.entry.word === entry.word &&
                cameraTarget.entry.sense_no === entry.sense_no;

              return (
                <Group
                  key={entryKey}
                  x={entry.map_x * WORLD_SCALE}
                  y={-entry.map_y * WORLD_SCALE}
                >
                  <Circle
                    radius={isHighlighted ? 9 : 7}
                    fill={getTileColor(entry.similarity)}
                    stroke={isHighlighted ? "#173a2a" : "#b9c5bd"}
                    strokeWidth={isHighlighted ? 2.5 : 1}
                    shadowColor={isHighlighted ? "#4f9d72" : "transparent"}
                    shadowBlur={isHighlighted ? 12 : 0}
                  />
                  <Text x={-55} y={13} width={110} align="center" text={entry.word} fontSize={13} fontStyle="bold" fill="#1d2b25" />
                  <Text x={-55} y={30} width={110} align="center" text={formatScaledSimilarity(entry.similarity)} fontSize={10} fill="#536159" />
                </Group>
              );
            })}
          </Layer>
        </Stage>
      </div>
    </div>
  );
}
