import React from "react";
import SectionWithMockup from "@/components/ui/section-with-mockup";

const exampleData1 = {
  title: (
    <>
      Intelligence,
      <br />
      delivered to you.
    </>
  ),
  description: (
    <>
      Get a tailored Monday morning brief directly in
      <br />
      your inbox, crafted by your virtual personal
      <br />
      analyst, spotlighting essential watchlist stories
      <br />
      and earnings for the week ahead.
    </>
  ),
  primaryImageSrc:
    "https://images.unsplash.com/photo-1556740749-887f6717d7e4?auto=format&fit=crop&w=1200&q=80",
  secondaryImageSrc:
    "https://images.unsplash.com/photo-1556740749-f5e8c1c69f55?auto=format&fit=crop&w=1200&q=80",
};

export function SectionMockupDemoPage() {
  return (
    <SectionWithMockup
      title={exampleData1.title}
      description={exampleData1.description}
      primaryImageSrc={exampleData1.primaryImageSrc}
      secondaryImageSrc={exampleData1.secondaryImageSrc}
    />
  );
}
