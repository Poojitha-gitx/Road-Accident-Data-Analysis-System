/**
 * Road Accident Data Analysis System
 * Frontend Interactions & Modal Controller
 */

document.addEventListener("DOMContentLoaded", () => {
    initModals();
    initAlerts();
    initFileDropzone();
});

/**
 * Modal open, close, and dynamic data pre-filling
 */
function initModals() {
    // Open modal buttons
    document.querySelectorAll("[data-modal-target]").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const targetId = btn.getAttribute("data-modal-target");
            const modal = document.getElementById(targetId);
            if (modal) {
                openModal(modal);
            }
        });
    });

    // Close buttons (X or Cancel)
    document.querySelectorAll(".modal-close, [data-modal-close]").forEach(btn => {
        btn.addEventListener("click", () => {
            const modal = btn.closest(".modal-backdrop");
            if (modal) {
                closeModal(modal);
            }
        });
    });

    // Click outside modal box to close
    document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
        backdrop.addEventListener("click", (e) => {
            if (e.target === backdrop) {
                closeModal(backdrop);
            }
        });
    });

    // ESC key closes any open modal
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-backdrop.open").forEach(m => closeModal(m));
        }
    });

    // Edit button click handler
    document.querySelectorAll(".btn-edit-record").forEach(btn => {
        btn.addEventListener("click", async () => {
            const recordId = btn.getAttribute("data-id");
            if (!recordId) return;

            try {
                const res = await fetch(`/api/record/${recordId}`);
                if (!res.ok) throw new Error("Could not retrieve record details");
                const data = await res.json();

                // Fill Edit Form
                const editModal = document.getElementById("editRecordModal");
                const editForm = document.getElementById("editRecordForm");
                
                editForm.action = `/records/edit/${recordId}`;
                document.getElementById("edit_accident_id_label").textContent = `#${data.accident_id}`;
                document.getElementById("edit_region").value = data.region || "";
                document.getElementById("edit_road_name").value = data.road_name || "";
                
                // Format datetime-local string (YYYY-MM-DDTHH:MM)
                let dtVal = data.accident_datetime_str || "";
                dtVal = dtVal.replace(" ", "T").substring(0, 16);
                document.getElementById("edit_accident_datetime").value = dtVal;

                document.getElementById("edit_vehicle_type").value = data.vehicle_type || "Car";
                document.getElementById("edit_severity").value = data.severity || "Minor";
                document.getElementById("edit_weather").value = data.weather || "Clear";

                openModal(editModal);
            } catch (err) {
                alert("Error loading record: " + err.message);
            }
        });
    });

    // Delete button click handler
    document.querySelectorAll(".btn-delete-record").forEach(btn => {
        btn.addEventListener("click", () => {
            const recordId = btn.getAttribute("data-id");
            const region = btn.getAttribute("data-region") || "";
            const dt = btn.getAttribute("data-dt") || "";

            const deleteModal = document.getElementById("deleteRecordModal");
            const deleteForm = document.getElementById("deleteRecordForm");

            deleteForm.action = `/records/delete/${recordId}`;
            document.getElementById("delete_record_summary").textContent = `Record #${recordId} (${region} - ${dt})`;

            openModal(deleteModal);
        });
    });
}

function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add("open");
    document.body.style.overflow = "hidden";
}

function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove("open");
    document.body.style.overflow = "";
}

/**
 * Auto-dismiss flash alerts
 */
function initAlerts() {
    const alerts = document.querySelectorAll(".flash-alert");
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.4s ease, transform 0.4s ease";
            alert.style.opacity = "0";
            alert.style.transform = "translateY(-6px)";
            setTimeout(() => alert.remove(), 400);
        }, 5500);
    });
}

/**
 * CSV Drag & Drop / File select preview
 */
function initFileDropzone() {
    const fileInput = document.getElementById("csv_file_input");
    const fileLabel = document.getElementById("csv_file_name_display");

    if (fileInput && fileLabel) {
        fileInput.addEventListener("change", () => {
            if (fileInput.files && fileInput.files.length > 0) {
                const file = fileInput.files[0];
                if (!file.name.toLowerCase().endsWith(".csv")) {
                    alert("Please select a file with .csv extension.");
                    fileInput.value = "";
                    fileLabel.textContent = "Click to browse or drop CSV here";
                    return;
                }
                fileLabel.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
            } else {
                fileLabel.textContent = "Click to browse or drop CSV here";
            }
        });
    }
}
