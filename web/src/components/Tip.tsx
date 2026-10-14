import {
  autoUpdate, flip, FloatingPortal, offset, safePolygon, shift, useDismiss, useFloating, useFocus, useHover,
  useInteractions, useRole, type Placement,
} from "@floating-ui/react";
import { useState, type ReactNode } from "react";

/** Explanatory tooltip: opens on hover and on keyboard focus, closes on Esc, portalled so table overflow doesn't
 *  clip it. The trigger is wrapped in an inline span (focusable when `focusable`). */
export function Tip({ content, children, placement = "top", focusable = true, className = "", interactive = false }: {
  content: ReactNode;
  children: ReactNode;
  placement?: Placement;
  focusable?: boolean;
  className?: string;
  /** The pointer can move into the tooltip (to click a link in it). */
  interactive?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({
    open, onOpenChange: setOpen, placement, whileElementsMounted: autoUpdate,
    middleware: [offset(6), flip(), shift({ padding: 8 })],
  });
  const { getReferenceProps, getFloatingProps } = useInteractions([
    useHover(context, { delay: { open: 150, close: 0 }, move: false, handleClose: interactive ? safePolygon() : null }),
    useFocus(context),
    useDismiss(context),
    useRole(context, { role: "tooltip" }),
  ]);
  if (!content) return <>{children}</>;
  return (
    <>
      <span ref={refs.setReference} className={`tip-trigger ${className}`} tabIndex={focusable ? 0 : undefined}
        {...getReferenceProps()}>
        {children}
      </span>
      {open && (
        <FloatingPortal>
          <div ref={refs.setFloating} style={floatingStyles} className="tip" {...getFloatingProps()}>{content}</div>
        </FloatingPortal>
      )}
    </>
  );
}

/** A hover card: like Tip, but it can be entered (to click links inside) and opens a bit later. A tap on a touch
 *  screen still follows the link underneath. */
export function HoverCard({ content, children, placement = "bottom-start" }: {
  content: () => ReactNode;
  children: ReactNode;
  placement?: Placement;
}) {
  const [open, setOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({
    open, onOpenChange: setOpen, placement, whileElementsMounted: autoUpdate,
    middleware: [offset(6), flip(), shift({ padding: 8 })],
  });
  const { getReferenceProps, getFloatingProps } = useInteractions([
    useHover(context, { delay: { open: 350, close: 120 }, handleClose: safePolygon() }),
    useDismiss(context),
    useRole(context, { role: "dialog" }),
  ]);
  return (
    <>
      <span ref={refs.setReference} className="hc-trigger" {...getReferenceProps()}>{children}</span>
      {open && (
        <FloatingPortal>
          <div ref={refs.setFloating} style={floatingStyles} className="hovercard" {...getFloatingProps()}>{content()}</div>
        </FloatingPortal>
      )}
    </>
  );
}
