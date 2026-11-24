"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  blur,
  ReducedMotionConfig,
  scale,
  spring,
  transition,
  useShouldReduceMotion,
  useTempoTransition,
} from "@animate-ui/react/utils/motion";

export function PressButton({
  className,
  disabled,
  label,
  type = "button",
}: {
  className?: string;
  disabled?: boolean;
  label: string;
  type?: "button" | "submit";
}) {
  return (
    <ReducedMotionConfig>
      <PressButtonMotion className={className} disabled={disabled} label={label} type={type} />
    </ReducedMotionConfig>
  );
}

function PressButtonMotion({
  className,
  disabled,
  label,
  type,
}: {
  className?: string;
  disabled?: boolean;
  label: string;
  type: "button" | "submit";
}) {
  const reduce = useShouldReduceMotion();
  const press = useTempoTransition(spring.press);
  const resize = useTempoTransition(spring.reflow);
  const swap = useTempoTransition(transition.swap);

  return (
    <motion.button
      className={className}
      type={type}
      disabled={disabled}
      layout
      aria-live="polite"
      initial={{ transform: "scale(1)" }}
      whileTap={{ transform: reduce ? "scale(1)" : `scale(${scale.press})` }}
      transition={{ ...press, layout: resize }}
    >
      <span className="btn-label">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={label}
            layout="position"
            initial={{ opacity: 0, filter: blur.icon }}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, filter: blur.icon, transition: swap }}
            transition={{ ...swap, layout: resize }}
          >
            {label}
          </motion.span>
        </AnimatePresence>
      </span>
    </motion.button>
  );
}

export function CuisineChip({
  selected,
  children,
  onClick,
}: {
  selected: boolean;
  children: string;
  onClick: () => void;
}) {
  const reduce = useShouldReduceMotion();
  const press = useTempoTransition(spring.press);

  return (
    <motion.button
      type="button"
      className={selected ? "on" : undefined}
      aria-pressed={selected}
      onClick={onClick}
      initial={{ transform: "scale(1)" }}
      whileTap={{ transform: reduce ? "scale(1)" : `scale(${scale.press})` }}
      transition={press}
    >
      {children}
    </motion.button>
  );
}

export function SoftLine({ className, children }: { className?: string; children: ReactNode }) {
  const reduce = useShouldReduceMotion();
  const reveal = useTempoTransition(transition.reveal);
  const rise = useTempoTransition(spring.entrance);

  return (
    <ReducedMotionConfig>
      <motion.p
        className={className}
        initial={{ opacity: 0, y: reduce ? 0 : 8 }}
        animate={{ opacity: 1, y: 0, transition: { ...rise, opacity: reveal } }}
      >
        {children}
      </motion.p>
    </ReducedMotionConfig>
  );
}

export function StatusBanner({ open, className, children }: { open: boolean; className?: string; children: ReactNode }) {
  const unfold = useTempoTransition(transition.disclosure);

  return (
    <ReducedMotionConfig>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="banner"
            className={className ? `banner-clip ${className}` : "banner-clip"}
            initial={{ height: 0, opacity: 0, filter: blur.disclosure }}
            animate={{ height: "auto", opacity: 1, filter: "blur(0px)" }}
            exit={{ height: 0, opacity: 0, filter: blur.disclosure, transition: unfold }}
            transition={unfold}
          >
            {children}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </ReducedMotionConfig>
  );
}

export function ResultItem({ index, children }: { index: number; children: ReactNode }) {
  const reduce = useShouldReduceMotion();
  const move = useTempoTransition(spring.reflow);
  const fade = useTempoTransition(transition.fade);

  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: reduce ? 0 : 8 }}
      animate={{
        opacity: 1,
        y: 0,
        transition: { ...move, opacity: fade, delay: reduce ? 0 : index * 0.08 },
      }}
      exit={{ opacity: 0, transition: fade }}
      transition={move}
    >
      {children}
    </motion.li>
  );
}
