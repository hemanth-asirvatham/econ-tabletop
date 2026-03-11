import { useState } from "react";

import { DevelopmentCard, PolicyCard } from "../state/types";
import { Card } from "./Card";

type DragPayload = {
  kind: "policy" | "development";
  id: string;
};

type Props = {
  faceUp: DevelopmentCard[];
  faceDown: DevelopmentCard[];
  implemented: PolicyCard[];
  attachments: Record<string, DevelopmentCard[]>;
  imageBaseUrl: string;
  selectedDevId: string | null;
  selectedPolicyId: string | null;
  onSelectDev: (id: string) => void;
  onSelectPolicy: (id: string) => void;
  onInspectDev: (card: DevelopmentCard) => void;
  onInspectPolicy: (card: PolicyCard) => void;
  onAttach: (policyId: string, devId: string) => void;
  onPlayPolicy: (policyId: string) => void;
};

export function Table({
  faceUp,
  faceDown,
  implemented,
  attachments,
  imageBaseUrl,
  selectedDevId,
  selectedPolicyId,
  onSelectDev,
  onSelectPolicy,
  onInspectDev,
  onInspectPolicy,
  onAttach,
  onPlayPolicy,
}: Props) {
  const [hoveredPolicyId, setHoveredPolicyId] = useState<string | null>(null);
  const [policyDropActive, setPolicyDropActive] = useState(false);

  function readPayload(event: React.DragEvent): DragPayload | null {
    const raw =
      event.dataTransfer.getData("application/x-econ-tabletop-card") ||
      event.dataTransfer.getData("text/plain");
    if (!raw) return null;
    try {
      const payload = JSON.parse(raw) as DragPayload;
      if (payload && (payload.kind === "policy" || payload.kind === "development")) {
        return payload;
      }
    } catch {
      return null;
    }
    return null;
  }

  return (
    <div className="board">
      <section className="board__column board__column--developments">
        <div className="board__section-header">
          <div>
            <p className="board__eyebrow">World board</p>
            <h3>Active developments</h3>
          </div>
          <span className="board__count">{faceUp.length}</span>
        </div>
        <div className="board__card-grid">
          {faceUp.length === 0 ? <div className="board__empty">No developments are active yet.</div> : null}
          {faceUp.map((dev) => (
            <Card
              key={dev.id}
              card={dev}
              type="development"
              imageBaseUrl={imageBaseUrl}
              variant="visual"
              selected={selectedDevId === dev.id}
              dragPayload={{ kind: "development", id: dev.id }}
              onClick={() => {
                onSelectDev(dev.id);
                onInspectDev(dev);
              }}
            />
          ))}
        </div>
      </section>

      <section className="board__column board__column--policy">
        <div className="board__section-header">
          <div>
            <p className="board__eyebrow">Policy table</p>
            <h3>Implemented responses</h3>
          </div>
          <span className="board__count">{implemented.length}</span>
        </div>
        <div
          className={`policy-dropzone${policyDropActive ? " policy-dropzone--active" : ""}`}
          onDragOver={(event) => event.preventDefault()}
          onDragEnter={() => setPolicyDropActive(true)}
          onDragLeave={() => setPolicyDropActive(false)}
          onDrop={(event) => {
            const payload = readPayload(event);
            if (payload?.kind === "policy") {
              onPlayPolicy(payload.id);
            }
            setPolicyDropActive(false);
          }}
        >
          {implemented.length === 0 ? (
            <div className="board__empty">Drag a policy here to spend budget and put it into play.</div>
          ) : (
            implemented.map((policy) => (
              <div
                key={policy.id}
                className={`policy-stack${hoveredPolicyId === policy.id ? " policy-stack--active" : ""}`}
                onDragOver={(event) => event.preventDefault()}
                onDragEnter={() => setHoveredPolicyId(policy.id)}
                onDragLeave={() => setHoveredPolicyId(null)}
                onDrop={(event) => {
                  const payload = readPayload(event);
                  if (payload?.kind === "development") {
                    onAttach(policy.id, payload.id);
                  }
                  setHoveredPolicyId(null);
                }}
              >
                <Card
                  card={policy}
                  type="policy"
                  imageBaseUrl={imageBaseUrl}
                  variant="visual"
                  selected={selectedPolicyId === policy.id}
                  dragPayload={{ kind: "policy", id: policy.id }}
                  onClick={() => {
                    onSelectPolicy(policy.id);
                    onInspectPolicy(policy);
                  }}
                />
                <div className="policy-stack__attachments">
                  {(attachments[policy.id] || []).map((dev) => (
                    <Card
                      key={dev.id}
                      card={dev}
                      type="development"
                      imageBaseUrl={imageBaseUrl}
                      variant="compact"
                      dragPayload={{ kind: "development", id: dev.id }}
                      onClick={() => onInspectDev(dev)}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="board__column board__column--forecast">
        <div className="board__section-header">
          <div>
            <p className="board__eyebrow">Forecast</p>
            <h3>Face-down queue</h3>
          </div>
          <span className="board__count">{faceDown.length}</span>
        </div>
        <div className="board__forecast-grid">
          {faceDown.length === 0 ? <div className="board__empty">No face-down cards are waiting to flip.</div> : null}
          {faceDown.map((dev) => (
            <Card
              key={dev.id}
              card={dev}
              type="development"
              imageBaseUrl={imageBaseUrl}
              variant="visual"
              faceDown
              selected={selectedDevId === dev.id}
              onClick={() => onSelectDev(dev.id)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
