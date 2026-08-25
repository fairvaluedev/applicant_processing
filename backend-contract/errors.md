# Standard Error Contract & Response Formats

## 1. Frappe Standard Error Response Envelope

All API errors returned by Frappe follow the canonical JSON envelope structure:

```json
{
  "exception": "frappe.exceptions.ValidationError: Error message here",
  "exc_type": "ValidationError",
  "_server_messages": "[\"{\\\"message\\\": \\\"Cannot generate CV: Applicant medical status is marked as 'UNFIT'.\\\", \\\"title\\\": \\\"Message\\\", \\\"indicator\\\": \\\"red\\\"}\"]",
  "message": "Human readable error description"
}
```

---

## 2. Standard HTTP Error Codes

| HTTP Code | Error Classification | Typical Cause / Scenarios | Error Message Example |
| :---: | :--- | :--- | :--- |
| **`400`** | **Bad Request** | Missing mandatory query parameters, malformed JSON payload. | `"Missing parameter: applicant_name"` |
| **`401`** | **Unauthorized** | Missing or invalid `Authorization: token <api_key>:<api_secret>` header or expired session cookie. | `"Invalid API key or secret"` |
| **`403`** | **Forbidden** | User lacks required role permission (e.g. Recruiter trying to edit financial ledgers). | `"Not permitted for DocType Income Expense Log"` |
| **`404`** | **Not Found** | Referenced Document ID does not exist. | `"Applicant APP-99999 does not exist"` |
| **`409`** | **Conflict / Timestamp Mismatch**| Concurrent edit collision (`TimestampMismatchError`). | `"Document has been modified after you have opened it. Please refresh."` |
| **`417`** | **Expectation Failed / Validation Error** | Business logic validation failure (e.g. `medical_status == 'UNFIT'`, unreached state step). | `"Cannot register applicant: Medical Status is marked as 'UNFIT'."` |
| **`422`** | **Link Validation Error** | Foreign key link value does not exist (e.g. invalid `Country` or `Contractor`). | `"Could not find Link Destination Country: Atlantis"` |
| **`500`** | **Internal Server Error**| Unhandled Python exception or database connectivity error. | `"Internal Server Error: check Frappe Error Log"` |

---

## 3. Frontend Error Parsing Utility (JavaScript/TypeScript Example)

```typescript
export function extractFrappeErrorMessage(errorResponse: any): string {
  if (!errorResponse) return "An unknown error occurred.";
  
  if (errorResponse.message) {
    return errorResponse.message;
  }
  
  if (errorResponse._server_messages) {
    try {
      const parsed = JSON.parse(errorResponse._server_messages);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const msgObj = JSON.parse(parsed[0]);
        if (msgObj.message) return msgObj.message;
      }
    } catch (e) {
      // Fallback
    }
  }
  
  if (errorResponse.exc_type) {
    return `${errorResponse.exc_type}: ${errorResponse.exception || ""}`;
  }
  
  return typeof errorResponse === "string" ? errorResponse : JSON.stringify(errorResponse);
}
```
