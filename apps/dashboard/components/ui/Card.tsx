import type * as React from "react";
import { cn } from "@/lib/utils";

type CardProps = React.ComponentPropsWithRef<"div">;
type CardTitleProps = React.ComponentPropsWithRef<"h3">;
type CardDescriptionProps = React.ComponentPropsWithRef<"p">;

function Card({ className, ref, ...props }: CardProps) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border bg-card text-card-foreground shadow",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ref, ...props }: CardProps) {
  return (
    <div
      ref={ref}
      className={cn("flex flex-col space-y-1.5 p-6", className)}
      {...props}
    />
  );
}

function CardTitle({ className, children, ref, ...props }: CardTitleProps) {
  return (
    <h3
      ref={ref}
      className={cn("font-semibold leading-none tracking-tight", className)}
      {...props}
    >
      {children}
    </h3>
  );
}

function CardContent({ className, ref, ...props }: CardProps) {
  return <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />;
}

function CardDescription({ className, ref, ...props }: CardDescriptionProps) {
  return (
    <p
      ref={ref}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent };
