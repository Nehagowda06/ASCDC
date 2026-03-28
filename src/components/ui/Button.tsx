import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
};

const variantClasses: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "border-blue-600 bg-blue-600 text-white hover:bg-blue-700 hover:border-blue-700",
  secondary: "border-gray-200 bg-white text-gray-900 hover:border-gray-300",
  danger: "border-red-500 bg-red-500 text-white hover:border-red-600 hover:bg-red-600",
};

export function Button({
  className,
  variant = "secondary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-xl border px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
