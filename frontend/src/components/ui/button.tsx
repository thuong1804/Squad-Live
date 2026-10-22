import type { ComponentProps } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("button", {
  variants: {
    variant: { default: "button-primary", outline: "button-outline", ghost: "button-ghost", danger: "button-danger" },
  },
  defaultVariants: { variant: "default" },
});
export function Button({
  className,
  variant,
  asChild = false,
  type = "button",
  ...props
}: ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }): React.JSX.Element {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      type={asChild ? undefined : type}
      className={cn(buttonVariants({ variant }), className)}
      {...props}
    />
  );
}
