"use client";

import { useEffect, useMemo, useState } from "react";

type SectionDefinition = {
  id: string;
  label: string;
  uploadedOnly?: boolean;
};

const sectionDefinitions: SectionDefinition[] = [
  { id: "findings", label: "Findings" },
  { id: "clarifications", label: "Clarifications", uploadedOnly: true },
  { id: "recommendations", label: "Recommendations" },
  { id: "remediation", label: "Remediation" },
  { id: "validation", label: "Validation" },
  { id: "package", label: "Package" },
  { id: "audit", label: "Audit trail", uploadedOnly: true },
];

export function SectionNavigator({ uploaded }: { uploaded: boolean }) {
  const sections = useMemo(
    () => sectionDefinitions.filter((section) => uploaded || !section.uploadedOnly),
    [uploaded],
  );
  const [activeSection, setActiveSection] = useState(sections[0].id);

  useEffect(() => {
    let frame = 0;
    function updateActiveSection() {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const targets = sections
          .map((section) => document.getElementById(section.id))
          .filter((target): target is HTMLElement => Boolean(target));
        if (targets.length === 0) return;

        const activationLine = 190;
        const passed = targets.filter(
          (target) => target.getBoundingClientRect().top <= activationLine,
        );
        const active = passed.at(-1) ?? targets[0];
        setActiveSection(active.id);
      });
    }

    const main = document.querySelector(".overview-main");
    const mutationObserver = new MutationObserver(updateActiveSection);
    if (main) {
      mutationObserver.observe(main, { childList: true, subtree: true });
    }
    window.addEventListener("scroll", updateActiveSection, { passive: true });
    window.addEventListener("resize", updateActiveSection);
    updateActiveSection();
    return () => {
      window.cancelAnimationFrame(frame);
      mutationObserver.disconnect();
      window.removeEventListener("scroll", updateActiveSection);
      window.removeEventListener("resize", updateActiveSection);
    };
  }, [sections]);

  function navigateTo(sectionId: string) {
    const target =
      document.getElementById(sectionId) ??
      document.getElementById("recommendations");
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(target.id);
  }

  return (
    <nav className="section-navigator" aria-label="Dataset workflow sections">
      <span className="section-navigator-label">Jump to</span>
      <div className="section-navigator-links">
        {sections.map((section) => (
          <button
            aria-current={activeSection === section.id ? "location" : undefined}
            key={section.id}
            onClick={() => navigateTo(section.id)}
            type="button"
          >
            {section.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
