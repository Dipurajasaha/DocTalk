You are an expert React + Tailwind UI engineer.

I already have a fully functional application. Your task is ONLY to redesign the frontend to exactly match the supplied UI while keeping all existing business logic, APIs, routing, authentication, database interactions, and backend functionality untouched.

## Rules

- DO NOT modify backend logic unless absolutely necessary.
- DO NOT rewrite existing API calls unless absolutely necessary.
- DO NOT change folder structure unless absolutely necessary.
- Preserve every existing feature.
- Only replace the presentation layer.
- Reuse existing data instead of creating mock data.
- Every button, form, modal, table and page must continue using the existing functionality.

## Tech Stack

Use:

- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide React icons
- Framer Motion (optional)
- CSS variables
- Responsive design

## UI Theme

Create a premium AI healthcare dashboard using soft neumorphism.

Background:

- Very light gray (#F5F5F7)
- Soft gradients
- Floating shadows
- Rounded corners (20–28px)
- Smooth transitions
- Large spacing
- Minimalistic interface

Cards:

- Neumorphic containers
- Dual box shadows
- Very subtle borders
- Soft hover animation

Buttons:

- Rounded
- Soft elevation
- Gradient hover
- Active pressed neumorphic effect

Typography:

- Clean
- Modern
- Large headings
- Medium body text
- Light gray secondary text

Animations:

- Smooth fade
- Slide transitions
- Hover scale
- Floating effects
- Loading animations
- Typing indicator

Scrollbar:

- Thin
- Minimal
- Rounded

## Application Layout

Create a 4-column full-height dashboard.

----------------------------------------------------

Left Sidebar (80px)

Contains:

- Logo
- History (make it a patient dashboard)
- AI Analysis
- Med Image Analysis
- Appointments
- Chat
- Settings at bottom

Active icon:

- Purple accent
- Neumorphic pressed effect

----------------------------------------------------

Chat History Sidebar

Contains:

- New Chat button
- Search (optional)
- Recent chats
- Scrollable history
- Active conversation highlighted
- Collapse button

----------------------------------------------------

Main Chat Area

Center panel should contain:

Top

- Greeting
- AI title
- Current chat information

Center

Conversation UI

User messages:

- Right aligned
- Purple bubble

Assistant messages:

- Left aligned
- Light neumorphic bubble

Support:

- Markdown
- Lists
- Code blocks
- Images
- Files

Bottom Input

Rounded AI input

Contains:

- Upload button
- Message textbox
- Send button
- Language selector
- Auto-growing textarea

Typing indicator

Smooth scrolling

----------------------------------------------------

Right Analysis Panel

Contains two tabs:

1. Upload

Drag & Drop upload area

Accept:

- PDF
- Images
- Reports
- Prescriptions


Show upload progress.

2. Documents

Display uploaded files as cards.

Each card includes:

- File icon
- Name
- Size
- Upload date
- Delete action

----------------------------------------------------

Background

Use an animated fluid gradient background similar to AI interfaces.

Very subtle.

Never distract from content.

----------------------------------------------------

Color Palette

Background:
#F5F5F7

Primary:
#7C5CFF

Accent:
#A88CFF

Text:
#1C1C1E

Secondary:
#6E6E73

Borders:
rgba(255,255,255,.6)

Shadow Light:
rgba(255,255,255,.8)

Shadow Dark:
rgba(209,209,214,.6)

----------------------------------------------------

Components

Create reusable components:

Layout
Sidebar
NavigationItem
ChatHistory
Conversation
MessageBubble
TypingIndicator
PromptInput
UploadArea
DocumentCard
AnalysisPanel
Header
Card
Modal
Button

----------------------------------------------------

Responsive

Desktop:
4-column layout

Tablet:
Collapse history panel

Mobile:
Drawer navigation
Bottom input fixed
Responsive chat

----------------------------------------------------

Accessibility

Keyboard navigation

ARIA labels

Focus states

Dark mode ready

----------------------------------------------------

Important

Whenever possible:

- Keep existing state management.
- Keep existing API hooks.
- Keep existing routes.
- Keep existing authentication.
- Keep existing database schema.
- Replace only JSX, styling, and layout.
- Do not generate fake data if real application data already exists.
- If some feature is unavailable, design the component and connect it to existing placeholders.

The final result should visually match the supplied UI while remaining fully compatible with the existing application's functionality.