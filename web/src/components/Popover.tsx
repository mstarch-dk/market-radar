import {
  autoUpdate, flip, FloatingFocusManager, FloatingPortal, offset, shift, useClick, useDismiss, useFloating, useInteractions,
  useRole,
} from "@floating-ui/react";
import { useState, type ReactNode } from "react";

/** A click-to-open panel (filter editors, column menu). Esc or a click outside closes it. */
export function Popover({ trigger, children, className = "", label }: {
  trigger: ReactNode;
  children: (close: () => void) => ReactNode;
  className?: string;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({
    open, onOpenChange: setOpen, placement: "bottom-start", whileElementsMounted: autoUpdate,
    middleware: [offset(4), flip(), shift({ padding: 8 })],
  });
  const { getReferenceProps, getFloatingProps } = useInteractions([useClick(context), useDismiss(context), useRole(context)]);
  return (
    <>
      <button ref={refs.setReference} type="button" className={`chip-btn ${open ? "open" : ""} ${className}`} aria-label={label}
        {...getReferenceProps()}>
        {trigger}
      </button>
      {open && (
        <FloatingPortal>
          <FloatingFocusManager context={context} modal={false}>
            <div ref={refs.setFloating} style={floatingStyles} className="popover" {...getFloatingProps()}>
              {children(() => setOpen(false))}
            </div>
          </FloatingFocusManager>
        </FloatingPortal>
      )}
    </>
  );
}
