import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
};

const variantClasses: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "border-[#C38EB4] bg-[#C38EB4] text-white hover:border-[#b47fa5] hover:bg-[#b47fa5]",
  secondary:
    "border-[#2b313b] bg-[#171b21] text-gray-100 hover:border-[#39404c] hover:bg-[#1b2028]",
  danger: "border-red-500 bg-red-500 text-white hover:border-red-600 hover:bg-red-600",
};

export function Button({
  className,
  variant = "secondary",
  type = "button",
  children,
  onClick,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-8.5 items-center justify-center rounded-lg border px-3 text-[12px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        className,
      )}
      onClick={onClick}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
