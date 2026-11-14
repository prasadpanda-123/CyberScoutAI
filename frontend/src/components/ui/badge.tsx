import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground border-border",
        success: "border-transparent bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
        warning: "border-transparent bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
        cyber: "border-transparent bg-cyber-blue/15 text-cyber-blue border-cyber-blue/30 font-mono",
        purple: "border-transparent bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/30",
        teal: "border-transparent bg-cyber-teal/15 text-cyber-teal border-cyber-teal/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export function CategoryBadge({ category }: { category?: string }) {
  if (!category) return null

  const catLower = category.toLowerCase()
  let variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "cyber" | "purple" | "teal" = "outline"

  if (catLower.includes("bounty") || catLower.includes("vdp")) {
    variant = "destructive"
  } else if (catLower.includes("internship") || catLower.includes("job")) {
    variant = "cyber"
  } else if (catLower.includes("ctf") || catLower.includes("hackathon")) {
    variant = "purple"
  } else if (catLower.includes("free") || catLower.includes("course") || catLower.includes("scholarship")) {
    variant = "success"
  } else if (catLower.includes("research") || catLower.includes("conference")) {
    variant = "teal"
  }

  return (
    <Badge variant={variant} className="font-medium">
      {category}
    </Badge>
  )
}

export { Badge, badgeVariants }

