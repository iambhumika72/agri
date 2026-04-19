import PropTypes from 'prop-types';
import { useState } from 'react';

/**
 * Thin coloured strip showing data freshness below section headers.
 * Green < 1h | Amber 1–6h | Red >6h
 */
export default function DataFreshnessBar({ updatedAt, label }) {
  const [hovered, setHovered] = useState(false);
  const now = Date.now();
  const updated = updatedAt ? new Date(updatedAt).getTime() : now - 2 * 60 * 1000;
  const diffMs = now - updated;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  const isGreen = diffMs < 3600000;
  const isAmber = diffMs >= 3600000 && diffMs < 21600000;
  const color = isGreen ? '#1D9E75' : isAmber ? '#BA7517' : '#A32D2D';
  const text = diffMin < 1 ? 'Just now' : diffMin < 60 ? `${diffMin}m ago` : `${diffHours}h ago`;

  return (
    <div
      className="relative flex items-center gap-2 group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="h-0.5 rounded-full flex-1 transition-all duration-300"
        style={{ backgroundColor: color, opacity: 0.6 }}
      />
      {hovered && (
        <span
          className="absolute left-0 -top-6 text-xs bg-neutral-800 text-white px-2 py-1 rounded whitespace-nowrap z-10"
          style={{ animation: 'fadeIn 150ms ease-out both' }}
        >
          {label || 'Data'} · Last updated: {text}
        </span>
      )}
      <span className="text-[10px] text-neutral-400 whitespace-nowrap flex-shrink-0">{text}</span>
    </div>
  );
}

DataFreshnessBar.propTypes = {
  updatedAt: PropTypes.string,
  label: PropTypes.string,
};
