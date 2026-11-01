"use client";

import { Copy, Download, Pencil, Share2, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogTrigger, DialogClose } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
  Menu,
  MenuCheckboxItem,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuRadioGroup,
  MenuRadioItem,
  MenuSeparator,
  MenuTrigger,
} from "@/components/ui/menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { Tooltip } from "@/components/ui/tooltip";

import { Demo, DocSection, State } from "./doc";

export function OverlaysSection() {
  const toast = useToast();
  const [showArchived, setShowArchived] = useState(false);
  const [sortBy, setSortBy] = useState("name");

  return (
    <DocSection
      id="overlays"
      title="Dialogs, sheets and menus"
      description="Layers that sit above the page. Each traps or manages focus, closes with Esc, and puts focus back where it was. On a phone, dialogs and sheets rise from the bottom with a grabber."
    >
      <Demo
        title="Dialog and sheet"
        note="A dialog is one focused task. The sheet is the 440 px inspector for previewing a record without losing your place."
      >
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="filled">Open a dialog</Button>
          </DialogTrigger>
          <DialogContent
            title="Add a location"
            description="Where people work. You can change this later."
            footer={
              <>
                <DialogClose asChild>
                  <Button variant="gray">Cancel</Button>
                </DialogClose>
                <DialogClose asChild>
                  <Button>Add location</Button>
                </DialogClose>
              </>
            }
          >
            <div className="flex flex-col gap-3">
              <TextField label="Location name" />
              <TextField label="Postcode" autoComplete="postal-code" />
            </div>
          </DialogContent>
        </Dialog>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="tinted">Open the inspector</Button>
          </SheetTrigger>
          <SheetContent
            title="Ada Lovelace"
            description="Operations Coordinator"
            footer={
              <>
                <Button variant="gray">Edit</Button>
                <Button>Open full record</Button>
              </>
            }
          >
            <div className="flex flex-col gap-3">
              <StatusChip status="expiring" />
              <p className="text-body text-label">
                Right to Work expires in 21 days. A new check is needed before 22 Nov 2026.
              </p>
            </div>
          </SheetContent>
        </Sheet>
      </Demo>

      <Demo
        title="Confirmations"
        note="The dialog starts with Cancel focused. Deleting something asks for its name. The inline version swaps in place."
      >
        <ConfirmDialog
          trigger={<Button variant="gray">Archive employee</Button>}
          title="Archive Ada Lovelace?"
          description="She will be hidden from lists and can be restored for 30 days."
          confirmLabel="Archive"
          onConfirm={() =>
            toast.show({
              title: "Ada Lovelace archived",
              tone: "success",
              action: { label: "Undo", onClick: () => {} },
            })
          }
        />
        <ConfirmDialog
          trigger={
            <Button variant="destructive">
              <Icon icon={Trash2} size={16} />
              Delete permanently
            </Button>
          }
          title="Delete Ada Lovelace for good?"
          description="This removes her record and documents. It cannot be undone."
          confirmLabel="Delete forever"
          destructive
          requireText="Ada Lovelace"
          onConfirm={() => toast.show({ title: "Deleted", tone: "danger" })}
        />
        <State label="Inline">
          <InlineConfirm
            label="Mark as left"
            prompt="Mark Ada as left?"
            confirmLabel="Mark as left"
            onConfirm={() => toast.show({ title: "Marked as left" })}
          />
        </State>
      </Demo>

      <Demo title="Menus, popovers and tooltips">
        <Menu>
          <MenuTrigger asChild>
            <Button variant="gray">Actions</Button>
          </MenuTrigger>
          <MenuContent>
            <MenuLabel>Employee</MenuLabel>
            <MenuItem icon={<Icon icon={Pencil} size={16} />} shortcut="E">
              Edit
            </MenuItem>
            <MenuItem icon={<Icon icon={Copy} size={16} />}>Duplicate</MenuItem>
            <MenuItem icon={<Icon icon={Share2} size={16} />}>Share a link</MenuItem>
            <MenuSeparator />
            <MenuCheckboxItem checked={showArchived} onCheckedChange={setShowArchived}>
              Show archived
            </MenuCheckboxItem>
            <MenuSeparator />
            <MenuLabel>Sort by</MenuLabel>
            <MenuRadioGroup value={sortBy} onValueChange={setSortBy}>
              <MenuRadioItem value="name">Name</MenuRadioItem>
              <MenuRadioItem value="start">Start date</MenuRadioItem>
            </MenuRadioGroup>
            <MenuSeparator />
            <MenuItem destructive icon={<Icon icon={Trash2} size={16} />}>
              Delete
            </MenuItem>
          </MenuContent>
        </Menu>
        <ContextMenu>
          <ContextMenuTrigger asChild>
            <div
              tabIndex={0}
              className="text-callout text-label bg-fill-secondary rounded-control grid h-14 w-64 place-items-center px-3 text-center"
            >
              Right-click here, or press Shift+F10
            </div>
          </ContextMenuTrigger>
          <ContextMenuContent>
            <ContextMenuItem icon={<Icon icon={Download} size={16} />}>Download</ContextMenuItem>
            <ContextMenuItem icon={<Icon icon={Copy} size={16} />}>Copy</ContextMenuItem>
            <ContextMenuSeparator />
            <ContextMenuItem destructive icon={<Icon icon={Trash2} size={16} />}>
              Delete
            </ContextMenuItem>
          </ContextMenuContent>
        </ContextMenu>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="tinted">Open a popover</Button>
          </PopoverTrigger>
          <PopoverContent label="Why a 14-day wait?" className="w-72 p-4">
            <p className="text-headline text-label">Why a 14-day wait?</p>
            <p className="text-callout text-label-secondary mt-1">
              New releases are not installed until the community has had two weeks to spot problems.
            </p>
          </PopoverContent>
        </Popover>
        <Tooltip content="Shown on hover and on keyboard focus">
          <Button variant="plain">Hover or focus me</Button>
        </Tooltip>
      </Demo>

      <Demo
        title="Toasts"
        note="Top centre. Hover or focus pauses them; F8 jumps to them. Anything reversible offers Undo and stays longer."
      >
        <Button variant="gray" onClick={() => toast.show({ title: "Changes saved" })}>
          Info
        </Button>
        <Button
          variant="gray"
          onClick={() =>
            toast.show({
              title: "Leave approved",
              description: "Ada Lovelace, 2 to 6 Nov 2026.",
              tone: "success",
              action: { label: "Undo", onClick: () => {} },
            })
          }
        >
          Success with Undo
        </Button>
        <Button
          variant="gray"
          onClick={() =>
            toast.show({
              title: "Check expires soon",
              description: "Right to Work for Grace Hopper, in 7 days.",
              tone: "warning",
            })
          }
        >
          Warning
        </Button>
        <Button
          variant="gray"
          onClick={() =>
            toast.show({
              title: "Could not save",
              description: "Check your connection and try again.",
              tone: "danger",
            })
          }
        >
          Error
        </Button>
      </Demo>
    </DocSection>
  );
}
