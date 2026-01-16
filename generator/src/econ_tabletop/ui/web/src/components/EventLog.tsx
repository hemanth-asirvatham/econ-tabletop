type Props = {
  log: string[];
};

export function EventLog({ log }: Props) {
  return (
    <section className="event-log">
      <div className="event-log__header">
        <h3>Event Log</h3>
        <p>Latest actions and milestones.</p>
      </div>
      <ul>
        {log.map((entry, index) => (
          <li key={`${entry}-${index}`}>{entry}</li>
        ))}
      </ul>
    </section>
  );
}
