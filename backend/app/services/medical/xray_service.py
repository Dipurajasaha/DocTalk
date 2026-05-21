"""X-ray formatting utilities.

Provides `format_xray_analysis_for_chat` used by routes to present AI
analysis results in a chat-friendly format.
"""

def format_xray_analysis_for_chat(analysis_result):
    if not analysis_result.get("success"):
        return f"❌ X-ray Analysis Failed: {analysis_result.get('error', 'Unknown error')}"

    analysis = analysis_result.get("analysis", {})
    images = analysis_result.get("images", {})

    output = []
    output.append("## 🩻 X-Ray Analysis Report")

    # Defect status
    if analysis.get("has_defect"):
        output.append(f"**Status**: ⚠️ Abnormality Detected")
        output.append(f"**Defect Type**: {analysis.get('defect_type', 'Unknown')}")
        output.append(f"**Location**: {analysis.get('location', 'Not specified')}")
        output.append(f"**Severity**: {analysis.get('severity', 'N/A')}/10")
        output.append(f"**Affected Area**: {analysis.get('affected_area', 'Unknown')}")
    else:
        output.append("**Status**: ✅ No significant abnormalities detected")

    output.append("")
    output.append("**Educational Recommendation**: " + analysis.get('recommendation', 'Consult with a healthcare professional for interpretation.'))

    # Images section
    if images:
        output.append("")
        output.append("### Visual Comparison")
        output.append("[Images will be displayed side-by-side below]")
        output.append("")

        left_col = []
        right_col = []

        if images.get("defect_marked"):
            left_col.append(f"**Left**: Defect Highlighted")
            left_col.append(f"![Defect Marked]({images['defect_marked']})")

        if images.get("healthy_version"):
            right_col.append(f"**Right**: Healthy Comparison (AI Generated)")
            right_col.append(f"![Healthy Version]({images['healthy_version']})")
        elif images.get("healthy_description"):
            right_col.append(f"**Educational Description of Healthy State**:")
            right_col.append(images["healthy_description"])

        output.extend(left_col)
        output.append("")
        output.extend(right_col)

    output.append("")
    output.append("---")
    output.append("⚠️ **IMPORTANT DISCLAIMER**: This AI analysis is for **educational purposes only**.")
    output.append("It is **NOT** a medical diagnosis. Please consult with a qualified radiologist or healthcare professional for accurate interpretation and clinical guidance.")


    return "\n".join(output)

__all__ = ["format_xray_analysis_for_chat", "xray_service"]

from typing import Dict, Any


class XRayService:
    async def format_for_chat(self, analysis_result: Dict[str, Any]) -> str:
        return format_xray_analysis_for_chat(analysis_result)


xray_service = XRayService()
