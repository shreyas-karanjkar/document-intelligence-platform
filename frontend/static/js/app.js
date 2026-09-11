const API_BASE_URL = "";

const processButton = document.getElementById("processButton");
const refreshHistoryButton = document.getElementById("refreshHistoryButton");

const documentType = document.getElementById("documentType");
const documentFile = document.getElementById("documentFile");

const uploadStatus = document.getElementById("uploadStatus");
const loadingSection = document.getElementById("loadingSection");
const resultSection = document.getElementById("resultSection");

const healthDot = document.getElementById("healthDot");
const healthText = document.getElementById("healthText");


// ------------------------------------------------------------
// Utility Functions
// ------------------------------------------------------------

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "-";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function formatNumber(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }

    const number = Number(value);

    if (Number.isNaN(number)) {
        return escapeHtml(value);
    }

    return number.toLocaleString("en-IN", {
        maximumFractionDigits: 2
    });
}


function formatDate(value) {
    if (!value) {
        return "-";
    }

    return String(value).replace("T", " ");
}


function setUploadStatus(message, type = "") {
    uploadStatus.textContent = message;
    uploadStatus.className = "status-message";

    if (type) {
        uploadStatus.classList.add(type);
    }
}


function showLoading(show) {
    if (show) {
        loadingSection.classList.remove("hidden");
        processButton.disabled = true;
    } else {
        loadingSection.classList.add("hidden");
        processButton.disabled = false;
    }
}


function getStatusClass(status) {
    if (!status) {
        return "";
    }

    const normalized = String(status).toUpperCase();

    if (normalized === "PASS") {
        return "status-pass";
    }

    if (normalized === "FAILED" || normalized === "FAIL") {
        return "status-fail";
    }

    if (normalized === "NOT_APPLICABLE") {
        return "status-na";
    }

    return "";
}


// ------------------------------------------------------------
// Health Check
// ------------------------------------------------------------

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/health`);

        if (!response.ok) {
            throw new Error("Health check failed");
        }

        const data = await response.json();

        healthDot.className = "health-dot online";
        healthText.textContent = data.status
            ? `API ${String(data.status).toUpperCase()}`
            : "API Online";

    } catch (error) {
        healthDot.className = "health-dot offline";
        healthText.textContent = "API Offline";
    }
}


// ------------------------------------------------------------
// Process Document
// ------------------------------------------------------------

async function processDocument() {

    const file = documentFile.files[0];

    if (!file) {
        setUploadStatus("Please select a document.", "error");
        return;
    }

    const selectedType = documentType.value;

    const allowedExtensions = [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png"
    ];

    const fileName = file.name.toLowerCase();

    const validExtension = allowedExtensions.some(
        extension => fileName.endsWith(extension)
    );

    if (!validExtension) {
        setUploadStatus(
            "Unsupported file type. Please upload PDF, JPG, JPEG or PNG.",
            "error"
        );
        return;
    }


    const formData = new FormData();

    formData.append("file", file);
    formData.append("document_type", selectedType);


    setUploadStatus("");
    showLoading(true);
    resultSection.classList.add("hidden");


    try {

        const response = await fetch(
            `${API_BASE_URL}/api/v1/documents/process`,
            {
                method: "POST",
                body: formData
            }
        );


        const data = await response.json();


        if (!response.ok) {

            const errorMessage =
                data.detail ||
                data.message ||
                "Document processing failed.";

            throw new Error(errorMessage);
        }


        displayResult(data);

        resultSection.classList.remove("hidden");

        setUploadStatus(
            "Document processed successfully.",
            "success"
        );

        await loadHistory();

    } catch (error) {

        console.error("Document processing error:", error);

        setUploadStatus(
            error.message || "Document processing failed.",
            "error"
        );

    } finally {

        showLoading(false);

    }
}


// ------------------------------------------------------------
// Display Complete Result
// ------------------------------------------------------------

function displayResult(data) {

    const extraction = data.extraction_result || {};
    const metadata = extraction.metadata || {};

    const validation =
        data.financial_validation_result || {};


    // Document header

    document.getElementById("resultDocumentName").textContent =
        data.document_name || "Document Result";


    document.getElementById("resultDocumentType").textContent =
        formatDocumentType(
            data.document_type || extraction.document_type
        );


    // Processing status

    const processingStatus =
        document.getElementById("processingStatus");

    processingStatus.textContent =
        data.processing_status || "-";

    processingStatus.className =
        `status-badge ${getStatusClass(data.processing_status)}`;


    // Metadata

    displayMetadata(metadata, extraction.periods || []);


    // Fields

    displayFields(extraction.fields || []);


    // Tables

    displayTables(extraction.tables || []);


    // Invoice line items

    displayInvoiceItems(
        extraction.invoice_line_items || []
    );


    // Financial validation

    displayValidation(validation);

}


// ------------------------------------------------------------
// Metadata
// ------------------------------------------------------------

function displayMetadata(metadata, periods) {

    const container =
        document.getElementById("metadataGrid");

    const metadataItems = [

        {
            label: "Document Title",
            value: metadata.document_title
        },

        {
            label: "Document Date",
            value: metadata.document_date
        },

        {
            label: "Entity",
            value: metadata.entity_name
        },

        {
            label: "Vendor",
            value: metadata.vendor_name
        },

        {
            label: "Customer",
            value: metadata.customer_name
        },

        {
            label: "Currency",
            value: metadata.currency
        },

        {
            label: "Periods",
            value: periods.length
                ? periods.join(", ")
                : null
        }

    ];


    container.innerHTML = metadataItems.map(item => {

        return `
            <div class="metadata-item">
                <span class="metadata-label">
                    ${escapeHtml(item.label)}
                </span>

                <span class="metadata-value">
                    ${escapeHtml(item.value)}
                </span>
            </div>
        `;

    }).join("");
}


// ------------------------------------------------------------
// Extracted Fields
// ------------------------------------------------------------

function displayFields(fields) {

    const tbody =
        document.getElementById("fieldsTableBody");


    if (!fields.length) {

        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    No extracted fields available.
                </td>
            </tr>
        `;

        return;
    }


    tbody.innerHTML = fields.map(field => {

        const evidence =
            field.evidence || {};


        return `
            <tr>

                <td>
                    <strong>
                        ${escapeHtml(field.field_name)}
                    </strong>
                </td>

                <td>
                    ${escapeHtml(field.value)}
                </td>

                <td>
                    ${escapeHtml(field.period)}
                </td>

                <td class="evidence-cell">
                    ${escapeHtml(evidence.source_text)}
                </td>

                <td>
                    ${escapeHtml(evidence.page_number)}
                </td>

            </tr>
        `;

    }).join("");
}


// ------------------------------------------------------------
// Extracted Tables
// ------------------------------------------------------------

function displayTables(tables) {

    const container =
        document.getElementById("tablesContainer");


    if (!tables.length) {

        container.innerHTML = `
            <div class="empty-state">
                No extracted tables available.
            </div>
        `;

        return;
    }


    container.innerHTML = tables.map((table, index) => {

        const columns = table.columns || [];
        const rows = table.rows || [];


        const headerHtml = columns.map(column => `
            <th>${escapeHtml(column)}</th>
        `).join("");


        const rowsHtml = rows.map(row => {

            return `
                <tr>
                    ${row.map(cell => `
                        <td>${escapeHtml(cell)}</td>
                    `).join("")}
                </tr>
            `;

        }).join("");


        return `
            <div class="extracted-table">

                <h3>
                    ${escapeHtml(
                        table.table_name ||
                        `Extracted Table ${index + 1}`
                    )}
                </h3>

                <div class="table-container">

                    <table>

                        <thead>
                            <tr>
                                ${headerHtml}
                            </tr>
                        </thead>

                        <tbody>
                            ${rowsHtml}
                        </tbody>

                    </table>

                </div>

                <small>
                    Page: ${escapeHtml(table.page_number)}
                </small>

            </div>
        `;

    }).join("");
}


// ------------------------------------------------------------
// Invoice Line Items
// ------------------------------------------------------------

function displayInvoiceItems(items) {

    const section =
        document.getElementById("invoiceSection");

    const tbody =
        document.getElementById("invoiceTableBody");


    if (!items.length) {

        section.classList.add("hidden");
        tbody.innerHTML = "";

        return;
    }


    section.classList.remove("hidden");


    tbody.innerHTML = items.map(item => {

        return `
            <tr>

                <td>
                    ${escapeHtml(item.description)}
                </td>

                <td>
                    ${formatNumber(item.quantity)}
                </td>

                <td>
                    ${formatNumber(item.unit_price)}
                </td>

                <td>
                    ${formatNumber(item.line_total)}
                </td>

            </tr>
        `;

    }).join("");
}


// ------------------------------------------------------------
// Financial Validation
// ------------------------------------------------------------

function displayValidation(validation) {

    const overallStatus =
        validation.overall_status || "NOT_APPLICABLE";


    const statusElement =
        document.getElementById(
            "validationOverallStatus"
        );


    statusElement.textContent =
        overallStatus;


    statusElement.className =
        `status-badge ${getStatusClass(overallStatus)}`;


    const tbody =
        document.getElementById(
            "validationTableBody"
        );


    const checks =
        validation.checks || [];


    if (!checks.length) {

        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    No financial validation checks available.
                </td>
            </tr>
        `;

        return;
    }


    tbody.innerHTML = checks.map(check => {

        return `
            <tr>

                <td>
                    <strong>
                        ${escapeHtml(check.check)}
                    </strong>
                </td>

                <td>
                    ${escapeHtml(check.formula)}
                </td>

                <td>
                    ${formatNumber(check.calculated)}
                </td>

                <td>
                    ${formatNumber(check.reported)}
                </td>

                <td>
                    ${formatNumber(check.variance)}
                </td>

                <td>
                    <span class="inline-status ${getStatusClass(check.status)}">
                        ${escapeHtml(check.status)}
                    </span>
                </td>

            </tr>
        `;

    }).join("");
}


// ------------------------------------------------------------
// Processing History
// ------------------------------------------------------------

async function loadHistory() {

    const tbody =
        document.getElementById(
            "historyTableBody"
        );


    try {

        const response =
            await fetch(
                `${API_BASE_URL}/api/v1/documents`
            );


        if (!response.ok) {
            throw new Error("Unable to load history.");
        }


        const data =
            await response.json();


        const documents =
            data.documents || [];


        if (!documents.length) {

            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-state">
                        No documents processed yet.
                    </td>
                </tr>
            `;

            return;
        }


        tbody.innerHTML = documents.map(document => {

            return `
                <tr>

                    <td>
                        ${escapeHtml(document.document_name)}
                    </td>

                    <td>
                        ${escapeHtml(
                            formatDocumentType(
                                document.document_type
                            )
                        )}
                    </td>

                    <td>
                        <span class="inline-status ${getStatusClass(document.processing_status)}">
                            ${escapeHtml(document.processing_status)}
                        </span>
                    </td>

                    <td>
                        ${escapeHtml(
                            formatDate(document.created_at)
                        )}
                    </td>

                    <td>
                        <button
                            class="view-button"
                            onclick="viewDocument(
                                '${encodeURIComponent(
                                    document.document_name
                                )}'
                            )"
                        >
                            View
                        </button>
                    </td>

                </tr>
            `;

        }).join("");


    } catch (error) {

        console.error(
            "History loading error:",
            error
        );


        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state error">
                    Unable to load processing history.
                </td>
            </tr>
        `;
    }
}


// ------------------------------------------------------------
// View Previous Document
// ------------------------------------------------------------

async function viewDocument(encodedName) {

    try {

        const response =
            await fetch(
                `${API_BASE_URL}/api/v1/documents/${encodedName}`
            );


        if (!response.ok) {
            throw new Error(
                "Unable to retrieve document."
            );
        }


        const data =
            await response.json();


        displayResult(data);

        resultSection.classList.remove("hidden");

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });


    } catch (error) {

        console.error(
            "Document retrieval error:",
            error
        );

        setUploadStatus(
            error.message,
            "error"
        );
    }
}


// ------------------------------------------------------------
// Document Type Formatting
// ------------------------------------------------------------

function formatDocumentType(type) {

    const labels = {

        invoice: "Invoice",

        balance_sheet: "Balance Sheet",

        profit_loss: "Profit & Loss",

        cash_flow: "Cash Flow Statement"

    };


    return labels[type] || type || "-";
}


// ------------------------------------------------------------
// Event Listeners
// ------------------------------------------------------------

processButton.addEventListener(
    "click",
    processDocument
);


refreshHistoryButton.addEventListener(
    "click",
    loadHistory
);


// ------------------------------------------------------------
// Initial Page Load
// ------------------------------------------------------------

checkHealth();
loadHistory();