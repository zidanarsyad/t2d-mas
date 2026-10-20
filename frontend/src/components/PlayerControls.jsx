import { Pause, Play, RotateCcw, StepBack, StepForward } from "lucide-react";

const SPEEDS = [0.5, 1, 2];

/** Play/Pause, previous, next, restart, speed and an optional scrub slider for useStepPlayer. */
export default function PlayerControls({ player, label = "Replay controls", scrub = true, valueText, stepName = "Step" }) {
  const { index, count, playing, speed } = player;
  if (!count) return null;
  return (
    <div className="player" role="group" aria-label={label}>
      <button type="button" className="button button-small" onClick={player.toggle} aria-pressed={playing}>
        {playing ? <Pause size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}
        {playing ? "Pause" : index >= count - 1 ? "Replay" : "Play"}
      </button>
      <button type="button" className="icon-button" onClick={player.prev} disabled={index === 0} aria-label={`Previous ${stepName.toLowerCase()}`}>
        <StepBack size={16} />
      </button>
      <button type="button" className="icon-button" onClick={player.next} disabled={index >= count - 1} aria-label={`Next ${stepName.toLowerCase()}`}>
        <StepForward size={16} />
      </button>
      <button type="button" className="icon-button" onClick={player.restart} aria-label="Restart from the beginning">
        <RotateCcw size={16} />
      </button>
      <div className="segmented" role="group" aria-label="Speed">
        {SPEEDS.map((value) => (
          <button key={value} type="button" className={`segment ${speed === value ? "is-selected" : ""}`} aria-pressed={speed === value} onClick={() => player.setSpeed(value)}>
            {value}×
          </button>
        ))}
      </div>
      {scrub && (
        <input
          className="scrubber"
          type="range"
          min={0}
          max={count - 1}
          value={index}
          onChange={(event) => player.seek(event.target.value)}
          aria-label={`${stepName} slider`}
          aria-valuetext={valueText || `${stepName} ${index + 1} of ${count}`}
        />
      )}
      <span className="player-count">
        {stepName} {index + 1} / {count}
      </span>
    </div>
  );
}
