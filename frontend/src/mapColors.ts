type ColorAnchor = {
  similarity: number;
  color: [number, number, number];
};

const COLOR_ANCHORS: ColorAnchor[] = [
  { similarity: 0.75, color: [190, 96, 78] },
  { similarity: 0.82, color: [241, 240, 234] },
  { similarity: 0.9, color: [183, 228, 187] },
  { similarity: 1, color: [91, 203, 132] },
];

function interpolateColor(start: number, end: number, position: number): number {
  return Math.round(start + (end - start) * position);
}

/** 원시 similarity를 타일의 비선형 발산형 색상으로 변환한다. */
export function getTileColor(similarity: number): string {
  if (similarity <= COLOR_ANCHORS[0].similarity) {
    return `rgb(${COLOR_ANCHORS[0].color.join(", ")})`;
  }

  for (let index = 1; index < COLOR_ANCHORS.length; index += 1) {
    const previous = COLOR_ANCHORS[index - 1];
    const current = COLOR_ANCHORS[index];

    if (similarity <= current.similarity) {
      const position =
        (similarity - previous.similarity) / (current.similarity - previous.similarity);
      const color = previous.color.map((channel, channelIndex) =>
        interpolateColor(channel, current.color[channelIndex], position),
      );
      return `rgb(${color.join(", ")})`;
    }
  }

  return `rgb(${COLOR_ANCHORS.at(-1)!.color.join(", ")})`;
}
