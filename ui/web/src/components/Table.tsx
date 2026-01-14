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
    <div style={{ display: "grid", gap: 24 }}>
      <Lane title="Face-up Developments">
        {faceUp.map((dev) => (
          <Card
            key={dev.id}
            card={dev}
            type="development"
            imageBaseUrl={imageBaseUrl}
            selected={selectedDevId === dev.id}
            dragPayload={{ kind: "development", id: dev.id }}
            onClick={() => onSelectDev(dev.id)}
          />
        ))}
      </Lane>
      <Lane title="Face-down Developments">
        {faceDown.map((dev) => (
          <Card
            key={dev.id}
            card={dev}
            type="development"
            imageBaseUrl={imageBaseUrl}
            selected={selectedDevId === dev.id}
            dragPayload={{ kind: "development", id: dev.id }}
            onClick={() => onSelectDev(dev.id)}
          />
        ))}
      </Lane>
      <Lane title="Dormant Developments">
        {dormant.map((dev) => (
          <Card
            key={dev.id}
            card={dev}
            type="development"
            imageBaseUrl={imageBaseUrl}
            selected={selectedDevId === dev.id}
            dragPayload={{ kind: "development", id: dev.id }}
            onClick={() => onSelectDev(dev.id)}
          />
        ))}
      </Lane>
      <Lane
        title="Implemented Policies"
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
        {implemented.map((policy) => (
          <div
            key={policy.id}
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
            style={{
              display: "grid",
              gap: 8,
              padding: 8,
              borderRadius: 10,
              border:
                hoveredPolicyId === policy.id
                  ? "2px dashed rgba(125, 211, 252, 0.7)"
                  : "1px solid rgba(148, 163, 184, 0.2)",
              background: "rgba(15, 23, 42, 0.6)",
            }}
          >
            <Card
              card={policy}
              type="policy"
              imageBaseUrl={imageBaseUrl}
              selected={selectedPolicyId === policy.id}
              onClick={() => onSelectPolicy(policy.id)}
            />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {(attachments[policy.id] || []).map((dev) => (
                <Card key={dev.id} card={dev} type="development" imageBaseUrl={imageBaseUrl} />
              ))}
            </div>
          </div>
        ))}
      </Lane>
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
}: {
  title: string;
  children: React.ReactNode;
  onDrop?: (event: React.DragEvent) => void;
  onDragEnter?: () => void;
  onDragLeave?: () => void;
  isActive?: boolean;
}) {
  return (
    <section>
      <h3 style={{ color: "#f8fafc" }}>{title}</h3>
      <div
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          padding: 12,
          borderRadius: 12,
          border: isActive ? "2px dashed rgba(125, 211, 252, 0.7)" : "1px dashed rgba(148, 163, 184, 0.15)",
          background: isActive ? "rgba(59, 130, 246, 0.08)" : "transparent",
          transition: "border 0.2s ease, background 0.2s ease",
        }}
      >
        {children}
      </div>
    </section>
  );
}
