import { render } from "@testing-library/react";
import { Skeleton } from "@/components/ui/Skeleton";

describe("Skeleton", () => {
  describe("default variant", () => {
    it("uses animate-pulse class by default", () => {
      const { container } = render(<Skeleton data-testid="skel" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("animate-pulse");
    });

    it("does not use animate-shimmer for default variant", () => {
      const { container } = render(<Skeleton />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).not.toContain("animate-shimmer");
    });
  });

  describe('variant="shimmer"', () => {
    it("uses animate-shimmer class", () => {
      const { container } = render(<Skeleton variant="shimmer" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("animate-shimmer");
    });

    it("does not use animate-pulse class", () => {
      const { container } = render(<Skeleton variant="shimmer" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).not.toContain("animate-pulse");
    });
  });

  describe("disableAnimation", () => {
    it("removes animate-pulse when disableAnimation is true", () => {
      const { container } = render(
        <Skeleton variant="text" disableAnimation />
      );
      const el = container.firstChild as HTMLElement;
      expect(el.className).not.toContain("animate-pulse");
      expect(el.className).not.toContain("animate-shimmer");
    });

    it("removes animate-shimmer when disableAnimation is true on shimmer variant", () => {
      const { container } = render(
        <Skeleton variant="shimmer" disableAnimation />
      );
      const el = container.firstChild as HTMLElement;
      expect(el.className).not.toContain("animate-shimmer");
      expect(el.className).not.toContain("animate-pulse");
    });
  });

  describe("dimension props", () => {
    it("applies numeric width and height as px", () => {
      const { container } = render(<Skeleton width={200} height={40} />);
      const el = container.firstChild as HTMLElement;
      expect(el.style.width).toBe("200px");
      expect(el.style.height).toBe("40px");
    });

    it("applies string width and height directly", () => {
      const { container } = render(<Skeleton width="50%" height="2rem" />);
      const el = container.firstChild as HTMLElement;
      expect(el.style.width).toBe("50%");
      expect(el.style.height).toBe("2rem");
    });

    it("does not set dimension styles when props are omitted", () => {
      const { container } = render(<Skeleton />);
      const el = container.firstChild as HTMLElement;
      // Style should not have explicit width/height set
      expect(el.style.width).toBe("");
      expect(el.style.height).toBe("");
    });
  });

  describe("variant shape classes", () => {
    it("text variant applies rounded class", () => {
      const { container } = render(<Skeleton variant="text" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("rounded");
    });

    it("circular variant applies rounded-full class", () => {
      const { container } = render(<Skeleton variant="circular" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("rounded-full");
    });

    it("rectangular variant applies rounded-none class", () => {
      const { container } = render(<Skeleton variant="rectangular" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("rounded-none");
    });

    it("rounded variant applies rounded-lg class", () => {
      const { container } = render(<Skeleton variant="rounded" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("rounded-lg");
    });
  });

  describe("custom className", () => {
    it("merges additional className", () => {
      const { container } = render(<Skeleton className="my-custom-class" />);
      const el = container.firstChild as HTMLElement;
      expect(el.className).toContain("my-custom-class");
    });
  });
});
