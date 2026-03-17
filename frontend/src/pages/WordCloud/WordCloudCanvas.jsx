import { useEffect, useRef, useCallback } from 'react';
import cloud from 'd3-cloud';

/**
 * WordCloudCanvas – Renders a word cloud using d3-cloud and SVG.
 *
 * @param {Array}  words               – Array of { text, value } objects
 * @param {number} width               – Canvas width
 * @param {number} height              – Canvas height
 * @param {string} className           – Additional CSS classes
 * @param {string} rotationMode        – "mixed" | "horizontal" | "vertical" | "custom"
 * @param {Array}  rotationAngles      – Array of angles, e.g. [0, 90] or [-45, 0, 45]
 * @param {number} rotationProbability – 0.0–1.0, probability of rotation for "mixed"
 * @param {Array}  highlightWords      – Array of word strings to highlight (participant's own words)
 */
function WordCloudCanvas({
  words = [],
  width = 600,
  height = 400,
  className = '',
  rotationMode = 'mixed',
  rotationAngles = [0, 90],
  rotationProbability = 0.5,
  highlightWords = [],
}) {
  const svgRef = useRef(null);

  const colorPalette = [
    '#2563eb', '#7c3aed', '#db2777', '#ea580c', '#16a34a',
    '#0891b2', '#4f46e5', '#c026d3', '#d97706', '#059669',
    '#6366f1', '#e11d48', '#0d9488', '#8b5cf6', '#f59e0b',
  ];

  const draw = useCallback((computedWords) => {
    const svg = svgRef.current;
    if (!svg) return;

    // Build a set of highlighted words (case-insensitive)
    const highlightSet = new Set(
      (highlightWords || []).map((w) => w.toLowerCase())
    );

    // Clear existing content
    while (svg.firstChild) {
      svg.removeChild(svg.firstChild);
    }

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('transform', `translate(${width / 2},${height / 2})`);

    computedWords.forEach((word, i) => {
      const isHighlighted = highlightSet.has(word.text.toLowerCase());

      // If highlighted, draw a background rect behind the text
      if (isHighlighted) {
        const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        // Approximate text dimensions
        const textWidth = word.text.length * word.size * 0.6;
        const textHeight = word.size * 1.2;
        bg.setAttribute('x', -textWidth / 2);
        bg.setAttribute('y', -textHeight * 0.75);
        bg.setAttribute('width', textWidth);
        bg.setAttribute('height', textHeight);
        bg.setAttribute('rx', '4');
        bg.setAttribute('ry', '4');
        bg.setAttribute('fill', 'rgba(0, 0, 0, 0.08)');
        bg.setAttribute('transform', `translate(${word.x},${word.y}) rotate(${word.rotate})`);
        g.appendChild(bg);
      }

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('font-size', `${word.size}px`);
      text.setAttribute('font-family', "'Inter', 'Segoe UI', 'Roboto', sans-serif");
      text.setAttribute('font-weight', word.size > 40 ? '700' : '500');
      text.setAttribute('fill', colorPalette[i % colorPalette.length]);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('transform', `translate(${word.x},${word.y}) rotate(${word.rotate})`);
      text.textContent = word.text;
      g.appendChild(text);
    });

    svg.appendChild(g);
  }, [width, height, colorPalette, highlightWords]);

  useEffect(() => {
    if (!words || words.length === 0) return;

    // Compute font sizes based on frequency
    const maxValue = Math.max(...words.map((w) => w.value));
    const minValue = Math.min(...words.map((w) => w.value));
    const minFontSize = 20;
    const maxFontSize = Math.min(120, Math.max(80, width / 8));

    const sizeScale = (value) => {
      if (maxValue === minValue) return (minFontSize + maxFontSize) / 2;
      return minFontSize + ((value - minValue) / (maxValue - minValue)) * (maxFontSize - minFontSize);
    };

    const layout = cloud()
      .size([width, height])
      .words(words.map((w) => ({ text: w.text, size: sizeScale(w.value), value: w.value })))
      .padding(5)
      .rotate(() => {
        const angles = Array.isArray(rotationAngles) && rotationAngles.length > 0
          ? rotationAngles : [0, 90];
        switch (rotationMode) {
          case 'horizontal':
            return 0;
          case 'vertical':
            return 90;
          case 'custom':
            return angles[Math.floor(Math.random() * angles.length)];
          case 'mixed':
          default:
            return Math.random() < rotationProbability
              ? angles[Math.floor(Math.random() * angles.length)]
              : 0;
        }
      })
      .fontSize((d) => d.size)
      .spiral('archimedean')
      .on('end', draw);

    layout.start();
  }, [words, width, height, draw, rotationMode, rotationAngles, rotationProbability]);

  if (!words || words.length === 0) {
    return (
      <div className={`wordcloud-empty ${className}`}>
        <p>Noch keine Wörter eingereicht.</p>
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className={`wordcloud-svg ${className}`}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
    />
  );
}

export default WordCloudCanvas;
