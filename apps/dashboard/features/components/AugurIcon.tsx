export default function AugurIcon({
  className = "w-6 h-6",
}: {
  className?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Central Core (The User/Mind) */}
      <path
        d="M50 30L67 40V60L50 70L33 60V40L50 30Z"
        stroke="currentColor"
        strokeWidth="6"
        fill="none"
        strokeLinejoin="round"
      />

      {/* Neural Core Dot */}
      <circle cx="50" cy="50" r="4" fill="currentColor" />

      {/* Orbital Nodes (The 3 Layers) */}
      {/* Top Node (Reasoning) */}
      <circle
        cx="50"
        cy="15"
        r="6"
        stroke="currentColor"
        strokeWidth="3"
        fill="none"
      />
      <line
        x1="50"
        y1="21"
        x2="50"
        y2="30"
        stroke="currentColor"
        strokeWidth="2"
      />

      {/* Bottom Right Node (Execution) */}
      <circle
        cx="80"
        cy="75"
        r="5"
        stroke="currentColor"
        strokeWidth="3"
        fill="none"
      />
      <line
        x1="67"
        y1="60"
        x2="76"
        y2="71"
        stroke="currentColor"
        strokeWidth="2"
      />

      {/* Bottom Left Node (Ops) */}
      <circle
        cx="20"
        cy="75"
        r="5"
        stroke="currentColor"
        strokeWidth="3"
        fill="none"
      />
      <line
        x1="33"
        y1="60"
        x2="24"
        y2="71"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}
