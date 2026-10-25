/**
 * Keyboard focus ring for controls that are not links.
 *
 * Links get their ring from the `a:focus-visible` rule in SettingsApp.css. Buttons and
 * `role="button"` elements get none, so this class shares that rule to keep both kinds of control
 * matching.
 */
export const FOCUS_RING_CLASS = 'wcar-focus-ring focus-visible:rounded-sm';
