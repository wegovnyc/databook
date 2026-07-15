<?php
/**
 * API endpoint for triggering dataset normalization.
 *
 * Why: The data scheduler on Databook2 needs to trigger the normalizer
 * for datasets requiring entity matching (orgs, districts, etc.).
 * This endpoint wraps the existing process_dataset.php logic as an
 * authenticated HTTP API.
 *
 * Usage: POST /normalizer/api_process.php?dataset_id=191
 * Header: Authorization: Bearer <API_TOKEN>
 * Response: {"status":"success","s3_url":"...","output":"..."}
 */

header('Content-Type: application/json');

// Only allow POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['status' => 'error', 'message' => 'Method not allowed. Use POST.']);
    exit;
}

require_once __DIR__ . '/../include/loader.php';

// Authenticate via Bearer token
$authHeader = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
$token = '';
if (preg_match('/^Bearer\s+(.+)$/i', $authHeader, $matches)) {
    $token = $matches[1];
}

if (empty($token) || $token !== API_TOKEN) {
    http_response_code(401);
    echo json_encode(['status' => 'error', 'message' => 'Invalid or missing API token.']);
    exit;
}

// Get dataset ID
$datasetId = $_GET['dataset_id'] ?? $_POST['dataset_id'] ?? null;
if (!$datasetId || !is_numeric($datasetId)) {
    http_response_code(400);
    echo json_encode(['status' => 'error', 'message' => 'Missing or invalid dataset_id parameter.']);
    exit;
}

$datasetId = (string)(int)$datasetId;

// Load dataset config
$ds = new DsList();
$ds->read(true);

if (!isset($ds->data[$datasetId])) {
    http_response_code(404);
    echo json_encode(['status' => 'error', 'message' => "Dataset ID $datasetId not found."]);
    exit;
}

$datasetConfig = $ds->data[$datasetId];
$output = [];
$output[] = "Processing dataset ID: $datasetId";
$output[] = "Name: " . ($datasetConfig['name'] ?? 'Unknown');

try {
    // 1. Initialize IndexTable
    $output[] = "Initializing IndexTable...";
    $i = new IndexTable($datasetConfig);

    if (!$i->checkSettings(true)) {
        http_response_code(500);
        echo json_encode(['status' => 'error', 'message' => 'Invalid settings for dataset.', 'output' => $output]);
        exit;
    }

    // 2. Fill Data (Matching)
    $output[] = "Running fillData (Matching)...";
    ob_start();
    $fillResult = $i->fillData(true);
    $fillOutput = ob_get_clean();
    if ($fillOutput) $output[] = $fillOutput;

    if (!$fillResult) {
        http_response_code(500);
        echo json_encode(['status' => 'error', 'message' => 'fillData failed.', 'output' => $output]);
        exit;
    }

    // 2.5. Re-apply agency mappings for CROL
    if ($datasetId == '191') {
        $output[] = "Re-applying CROL agency mappings...";
        $patchCmd = "cd " . escapeshellarg(ROOTDIR) . " && python3 final_patch.py 2>&1";
        $patchOutput = shell_exec($patchCmd);
        if ($patchOutput) $output[] = trim($patchOutput);
        $i->load();
        $output[] = "Index reloaded after patch.";
    }

    $ds->setIndexFillingDate($datasetId, false);

    // 3. Transform and Write (Normalization & Upload)
    $output[] = "Compiling and transforming dataset...";
    $dataset = new Dataset($i);


    ob_start();
    $transformResult = $dataset->isValid && $dataset->transform();
    $transformOutput = ob_get_clean();
    if ($transformOutput) $output[] = $transformOutput;


    // transform() returns false if any entities are unmatched, but still
    // writes ALL rows (including unmatched) to the temp CSV. We proceed
    // with S3 upload regardless, reporting unmatched entities as warnings.
    $hasWarnings = !$transformResult;
    $warnings = [];
    if ($transformOutput && $hasWarnings) {
        // Extract unmatched entity names from the output
        preg_match_all("/Source text '([^']+)' was not matched/", $transformOutput, $matches);
        $warnings = $matches[1] ?? [];
        $output[] = count($warnings) . " unmatched entities (will proceed with upload)";
    }

    // Attempt S3 upload — the temp file has data even with partial matches
    if ($dataset->isValid) {
        $dataset->write();

        $outputUrl = $dataset->outputUrl();
        $output[] = "Success! Output: $outputUrl";

        $ds->setLastUpdated($datasetId, $outputUrl, '');
        $i->saveCache();
        $ds->updateStats($datasetId);

        $response = [
            'status' => 'success',
            's3_url' => $outputUrl,
            'dataset_id' => $datasetId,
            'name' => $datasetConfig['name'] ?? '',
            'output' => $output
        ];
        if (!empty($warnings)) {
            $response['warnings'] = $warnings;
        }
        echo json_encode($response);
    } else {
        http_response_code(500);
        echo json_encode(['status' => 'error', 'message' => 'Transformation failed.', 'output' => $output]);
    }
} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode([
        'status' => 'error',
        'message' => $e->getMessage(),
        'trace' => $e->getTraceAsString(),
        'output' => $output
    ]);
}
