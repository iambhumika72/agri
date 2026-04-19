/**
 * FarmerInputForm.jsx
 * ====================
 * React component for submitting field observations from the Agri platform.
 *
 * Features:
 *  - Controlled form with validation before submission.
 *  - Dropdowns sourced from the same crop/issue list as the backend config.
 *  - Severity radio buttons with colour-coded labels.
 *  - Async POST to /farmer-input/mobile with loading and error/success states.
 *  - Mobile-responsive layout using Tailwind CSS utility classes.
 *
 * Props: none  (self-contained, reads API_BASE_URL from env if available)
 */

import React, { useState } from "react";

// ---------------------------------------------------------------------------
// Configuration — mirror configs/farmer_input_config.yaml
// ---------------------------------------------------------------------------
const CROP_TYPES = [
  "wheat", "rice", "maize", "cotton", "sugarcane",
  "soybean", "groundnut", "millet", "sorghum", "tomato",
  "potato", "onion", "chilli", "mustard", "barley",
];

const ISSUE_TYPES = ["pest", "disease", "drought", "flood", "other"];

const SEVERITY_OPTIONS = [
  { value: "low",    label: "Low",    colour: "text-green-600" },
  { value: "medium", label: "Medium", colour: "text-yellow-600" },
  { value: "high",   label: "High",   colour: "text-red-600" },
];

const API_BASE_URL =
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helper — format today's date as YYYY-MM-DD for <input type="date">
// ---------------------------------------------------------------------------
function todayISO() {
  return new Date().toISOString().split("T")[0];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Reusable labelled form field wrapper. */
function FormField({ label, htmlFor, required, children, error }) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-sm font-semibold text-gray-700 dark:text-gray-300"
      >
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {children}
      {error && (
        <p className="text-xs text-red-500 mt-0.5" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/** A styled <input> element. */
function TextInput({ id, value, onChange, placeholder, type = "text", ...rest }) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className={[
        "w-full rounded-lg border border-gray-300 dark:border-gray-600",
        "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
        "px-3 py-2 text-sm placeholder-gray-400",
        "focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent",
        "transition-colors duration-150",
      ].join(" ")}
      {...rest}
    />
  );
}

/** A styled <select> element. */
function SelectInput({ id, value, onChange, children }) {
  return (
    <select
      id={id}
      value={value}
      onChange={onChange}
      className={[
        "w-full rounded-lg border border-gray-300 dark:border-gray-600",
        "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
        "px-3 py-2 text-sm",
        "focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent",
        "transition-colors duration-150 cursor-pointer",
      ].join(" ")}
    >
      {children}
    </select>
  );
}

/** Inline feedback banner (success or error). */
function FeedbackBanner({ type, message }) {
  if (!message) return null;
  const styles =
    type === "success"
      ? "bg-green-50 border-green-400 text-green-800 dark:bg-green-900/30 dark:text-green-300"
      : "bg-red-50 border-red-400 text-red-800 dark:bg-red-900/30 dark:text-red-300";

  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${styles}`}
    >
      <span className="mt-0.5 text-lg">{type === "success" ? "✅" : "❌"}</span>
      <p>{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validateForm(fields) {
  const errors = {};

  if (!fields.farmer_id.trim()) {
    errors.farmer_id = "Farmer ID is required.";
  } else if (!/^[A-Za-z0-9_\-]{1,64}$/.test(fields.farmer_id.trim())) {
    errors.farmer_id = "Only letters, numbers, underscores, and hyphens allowed.";
  }

  if (!fields.location.trim()) {
    errors.location = "Village or coordinates are required.";
  }

  if (!fields.crop_type) {
    errors.crop_type = "Please select a crop type.";
  }

  if (!fields.observed_issue) {
    errors.observed_issue = "Please select an issue type.";
  }

  if (!fields.severity) {
    errors.severity = "Please select a severity level.";
  }

  if (!fields.date_observed) {
    errors.date_observed = "Date of observation is required.";
  } else if (new Date(fields.date_observed) > new Date()) {
    errors.date_observed = "Date cannot be in the future.";
  }

  if (fields.additional_notes && fields.additional_notes.length > 1000) {
    errors.additional_notes = "Notes must be 1000 characters or fewer.";
  }

  return errors;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function FarmerInputForm() {
  // ----- Form state -----
  const [fields, setFields] = useState({
    farmer_id: "",
    location: "",
    crop_type: "",
    observed_issue: "",
    severity: "",
    date_observed: todayISO(),
    additional_notes: "",
  });

  // ----- UI state -----
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null); // { type, message }

  // ----- Handlers -----
  function handleChange(e) {
    const { id, value } = e.target;
    setFields((prev) => ({ ...prev, [id]: value }));
    // Clear the field-level error on change
    if (errors[id]) {
      setErrors((prev) => ({ ...prev, [id]: undefined }));
    }
  }

  function handleSeverityChange(value) {
    setFields((prev) => ({ ...prev, severity: value }));
    if (errors.severity) {
      setErrors((prev) => ({ ...prev, severity: undefined }));
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFeedback(null);

    // Validate
    const validationErrors = validateForm(fields);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/farmer-input/mobile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...fields,
          farmer_id: fields.farmer_id.trim(),
          location: fields.location.trim(),
          additional_notes: fields.additional_notes.trim() || undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFeedback({
          type: "success",
          message: `Observation recorded! Record ID: ${data.record_id}`,
        });
        // Reset form fields (keep farmer_id for convenience)
        setFields((prev) => ({
          ...prev,
          location: "",
          crop_type: "",
          observed_issue: "",
          severity: "",
          date_observed: todayISO(),
          additional_notes: "",
        }));
        setErrors({});
      } else {
        const errData = await response.json().catch(() => ({}));
        const detail =
          errData?.detail ||
          (Array.isArray(errData?.detail)
            ? errData.detail.map((d) => d.msg).join(", ")
            : "Submission failed. Please check your inputs.");
        setFeedback({ type: "error", message: String(detail) });
      }
    } catch (networkErr) {
      setFeedback({
        type: "error",
        message: `Network error: ${networkErr.message}. Please check your connection.`,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  // ----- Render -----
  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Card */}
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-green-600 to-emerald-500 px-6 py-5">
            <div className="flex items-center gap-3">
              <span className="text-3xl" aria-hidden="true">🌾</span>
              <div>
                <h1 className="text-xl font-bold text-white">Field Observation Report</h1>
                <p className="text-green-100 text-sm mt-0.5">
                  Submit a farm observation for AI-powered advisory
                </p>
              </div>
            </div>
          </div>

          {/* Form body */}
          <form
            onSubmit={handleSubmit}
            noValidate
            aria-label="Farmer Input Submission Form"
            className="px-6 py-6 flex flex-col gap-5"
          >
            {/* Farmer ID */}
            <FormField
              label="Farmer ID"
              htmlFor="farmer_id"
              required
              error={errors.farmer_id}
            >
              <TextInput
                id="farmer_id"
                value={fields.farmer_id}
                onChange={handleChange}
                placeholder="e.g. F042"
                autoComplete="off"
              />
            </FormField>

            {/* Village / Location */}
            <FormField
              label="Village or Coordinates"
              htmlFor="location"
              required
              error={errors.location}
            >
              <TextInput
                id="location"
                value={fields.location}
                onChange={handleChange}
                placeholder='e.g. "Nashik" or "19.9975,73.7898"'
              />
            </FormField>

            {/* Two-column row: Crop Type + Issue Observed */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField
                label="Crop Type"
                htmlFor="crop_type"
                required
                error={errors.crop_type}
              >
                <SelectInput
                  id="crop_type"
                  value={fields.crop_type}
                  onChange={handleChange}
                >
                  <option value="" disabled>Select crop…</option>
                  {CROP_TYPES.map((c) => (
                    <option key={c} value={c}>
                      {c.charAt(0).toUpperCase() + c.slice(1)}
                    </option>
                  ))}
                </SelectInput>
              </FormField>

              <FormField
                label="Issue Observed"
                htmlFor="observed_issue"
                required
                error={errors.observed_issue}
              >
                <SelectInput
                  id="observed_issue"
                  value={fields.observed_issue}
                  onChange={handleChange}
                >
                  <option value="" disabled>Select issue…</option>
                  {ISSUE_TYPES.map((i) => (
                    <option key={i} value={i}>
                      {i.charAt(0).toUpperCase() + i.slice(1)}
                    </option>
                  ))}
                </SelectInput>
              </FormField>
            </div>

            {/* Severity */}
            <FormField label="Severity" htmlFor="severity" required error={errors.severity}>
              <div
                role="radiogroup"
                aria-label="Severity level"
                className="flex gap-3 flex-wrap"
              >
                {SEVERITY_OPTIONS.map(({ value, label, colour }) => {
                  const isSelected = fields.severity === value;
                  return (
                    <label
                      key={value}
                      className={[
                        "flex items-center gap-2 cursor-pointer select-none",
                        "rounded-lg border-2 px-4 py-2 text-sm font-medium transition-all duration-150",
                        isSelected
                          ? `border-current ${colour} bg-opacity-10 bg-current shadow-sm`
                          : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-gray-300",
                      ].join(" ")}
                    >
                      <input
                        type="radio"
                        name="severity"
                        value={value}
                        checked={isSelected}
                        onChange={() => handleSeverityChange(value)}
                        className="sr-only"
                      />
                      <span
                        className={`h-3 w-3 rounded-full ${
                          value === "low"
                            ? "bg-green-500"
                            : value === "medium"
                            ? "bg-yellow-500"
                            : "bg-red-500"
                        }`}
                        aria-hidden="true"
                      />
                      {label}
                    </label>
                  );
                })}
              </div>
            </FormField>

            {/* Date Observed */}
            <FormField
              label="Date Observed"
              htmlFor="date_observed"
              required
              error={errors.date_observed}
            >
              <TextInput
                id="date_observed"
                type="date"
                value={fields.date_observed}
                onChange={handleChange}
                max={todayISO()}
              />
            </FormField>

            {/* Additional Notes */}
            <FormField
              label="Additional Notes"
              htmlFor="additional_notes"
              error={errors.additional_notes}
            >
              <textarea
                id="additional_notes"
                value={fields.additional_notes}
                onChange={handleChange}
                placeholder="Describe what you observed in detail…"
                rows={4}
                maxLength={1000}
                className={[
                  "w-full rounded-lg border border-gray-300 dark:border-gray-600",
                  "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                  "px-3 py-2 text-sm placeholder-gray-400 resize-none",
                  "focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent",
                  "transition-colors duration-150",
                ].join(" ")}
              />
              <p className="text-xs text-gray-400 text-right mt-0.5">
                {fields.additional_notes.length} / 1000
              </p>
            </FormField>

            {/* Feedback banner */}
            <FeedbackBanner type={feedback?.type} message={feedback?.message} />

            {/* Submit button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className={[
                "w-full rounded-xl py-3 px-6 font-semibold text-sm text-white",
                "bg-gradient-to-r from-green-600 to-emerald-500",
                "hover:from-green-700 hover:to-emerald-600",
                "focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2",
                "transition-all duration-200 shadow-md",
                isSubmitting ? "opacity-60 cursor-not-allowed" : "hover:shadow-lg active:scale-95",
              ].join(" ")}
              aria-busy={isSubmitting}
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg
                    className="animate-spin h-4 w-4 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <circle
                      className="opacity-25"
                      cx="12" cy="12" r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                    />
                  </svg>
                  Submitting…
                </span>
              ) : (
                "Submit Observation"
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="border-t border-gray-100 dark:border-gray-800 px-6 py-3 bg-gray-50 dark:bg-gray-900/50">
            <p className="text-xs text-center text-gray-400">
              Agri Platform · Farmer Input Module · Powered by Generative AI
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
