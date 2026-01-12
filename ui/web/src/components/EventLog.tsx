type Props = {
  log: string[];
};

export function EventLog({ log }: Props) {
  return (
    <section style={{ background: "#0f172a", padding: 12, borderRadius: 8 }}>
      <h3 style={{ color: "#f8fafc" }}>Event Log</h3>
      <ul style={{ color: "#cbd5f5" }}>
        {log.map((entry, index) => (
          <li key={`${entry}-${index}`}>{entry}</li>
        ))}
      </ul>
    </section>
  );
}
