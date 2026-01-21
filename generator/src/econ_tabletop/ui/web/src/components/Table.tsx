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
  dormant: DevelopmentCard[];
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
  dormant,
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
    } catch (error) {
      return null;
    }
    return null;
  }

  return (
    <div className="table">
      <div className="table__grid">
        <Lane title="Development Board" className="lane lane--developments">
          {[...faceUp, ...dormant].map((dev) => (
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
          {faceDown.map((dev) => (
            <Card
              key={dev.id}
              card={dev}
              type="development"
              imageBaseUrl={imageBaseUrl}
              variant="visual"
              faceDown
              selected={selectedDevId === dev.id}
              dragPayload={{ kind: "development", id: dev.id }}
              onClick={() => onSelectDev(dev.id)}
            />
          ))}
        </Lane>

        <Lane
          title="Policy Center"
          className="lane lane--policy"
          onDrop={(event) => {
            const payload = readPayload(event);
            if (payload?.kind === "policy") {
              onPlayPolicy(payload.id);
            }
            setPolicyDropActive(false);
          }}
          onDragEnter={() => setPolicyDropActive(true)}
          onDragLeave={() => setPolicyDropActive(false)}
          isActive={policyDropActive}
        >
          {implemented.length === 0 ? (
            <div className="lane__empty">Drag policies here to implement them.</div>
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
        </Lane>
      </div>
    </div>
  );
}

function Lane({
  title,
  children,
  onDrop,
  onDragEnter,
  onDragLeave,
  isActive,
  className,
}: {
  title: string;
  children: React.ReactNode;
  onDrop?: (event: React.DragEvent) => void;
  onDragEnter?: () => void;
  onDragLeave?: () => void;
  isActive?: boolean;
  className?: string;
}) {
  return (
    <section className={`${className ?? "lane"}${isActive ? " lane--active" : ""}`}>
      <div className="lane__header">
        <h3>{title}</h3>
      </div>
      <div
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        className="lane__body"
      >
        {children}
      </div>
    </section>
  );
}
