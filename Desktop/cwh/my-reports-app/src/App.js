import React, { useState, useRef } from 'react';

// Load external libraries via CDN for client-side processing
// PapaParse for CSV parsing
// JSZip for creating zip files
// FileSaver for saving the generated zip file
const loadScript = (src) => {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
};

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [downloadLink, setDownloadLink] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [progressMessage, setProgressMessage] = useState('');
  const fileInputRef = useRef(null);

  // Function to handle file selection
  const handleFileChange = (event) => {
    const file = event.target.files[0];
    setSelectedFile(file);
    setDownloadLink(null); // Reset download link on new file selection
    setErrorMessage(''); // Clear any previous errors
    setProgressMessage(''); // Clear progress message
  };

  // Function to process the CSV file
  const processCsv = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select a CSV file first.');
      return;
    }

    setProcessing(true);
    setErrorMessage('');
    setDownloadLink(null);
    setProgressMessage('Loading necessary libraries...');

    try {
      // Dynamically load libraries
      await loadScript('https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.3.0/papaparse.min.js');
      await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js');
      await loadScript('https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js');

      setProgressMessage('Reading CSV file...');

      const reader = new FileReader();
      reader.onload = async (e) => {
        const csvText = e.target.result;

        setProgressMessage('Parsing CSV data...');
        // Parse CSV using PapaParse
        // header: true means the first row will be used as column headers
        // dynamicTyping: true attempts to convert values to their appropriate types (numbers, booleans)
        // skipEmptyLines: true ignores empty rows
        const { data, errors, meta } = PapaParse.parse(csvText, {
          header: true,
          dynamicTyping: false, // Keep as string for consistent CSV output
          skipEmptyLines: true,
          error: (error) => {
            console.error("PapaParse error:", error);
            setErrorMessage(`CSV parsing error: ${error.message}`);
            setProcessing(false);
            return;
          }
        });

        if (errors.length > 0) {
          setErrorMessage(`CSV parsing errors detected: ${errors.map(err => err.message).join(', ')}`);
          setProcessing(false);
          return;
        }

        const developmentColumn = 'Development Name??';

        // Check if the required column exists
        if (!meta.fields || !meta.fields.includes(developmentColumn)) {
          setErrorMessage(`Error: Column '${developmentColumn}' not found in the CSV file. Please ensure the header is correct.`);
          setProcessing(false);
          return;
        }

        setProgressMessage('Grouping data by development...');

        // Group data by 'Development Name??'
        const groupedData = {};
        data.forEach(row => {
          const devName = row[developmentColumn];
          if (devName) { // Ensure development name is not empty or null
            if (!groupedData[devName]) {
              groupedData[devName] = [];
            }
            groupedData[devName].push(row);
          }
        });

        const uniqueDevelopments = Object.keys(groupedData);
        if (uniqueDevelopments.length === 0) {
          setErrorMessage('No valid development names found to group by.');
          setProcessing(false);
          return;
        }

        setProgressMessage(`Generating ${uniqueDevelopments.length} individual CSV files...`);

        const zip = new JSZip();
        // Add a folder for the reports inside the zip
        const reportsFolder = zip.folder('Monthly_Reports');

        // Get all headers from the original CSV to ensure consistent columns in output files
        const allHeaders = meta.fields;

        uniqueDevelopments.forEach((devName, index) => {
          // Sanitize development name for filename
          const safeDevName = devName.replace(/[^a-zA-Z0-9\s-]/g, '').replace(/\s+/g, '_').trim();
          if (!safeDevName) {
            console.warn(`Skipping development with unprocessable name: "${devName}"`);
            return;
          }

          // Convert grouped data back to CSV string
          // Ensure all output CSVs have the same headers as the original
          const devCsvContent = PapaParse.unparse({
            fields: allHeaders, // Use all original headers
            data: groupedData[devName]
          });

          // Add each CSV to the zip file
          reportsFolder.file(`${safeDevName}_Report.csv`, devCsvContent);
          setProgressMessage(`Generating files... (${index + 1}/${uniqueDevelopments.length})`);
        });

        setProgressMessage('Compressing files into a ZIP archive...');

        // Generate the zip file as a Blob
        const zipBlob = await zip.generateAsync({ type: 'blob' });

        // Create a download URL for the zip file
        const url = URL.createObjectURL(zipBlob);
        setDownloadLink(url);
        setProgressMessage('Processing complete! Your download is ready.');
        setProcessing(false);

        // Optionally trigger immediate download
        // saveAs(zipBlob, `Monthly_Reports_${new Date().getFullYear()}-${(new Date().getMonth() + 1).toString().padStart(2, '0')}.zip`);

      };
      reader.readAsText(selectedFile); // Read the file as plain text
    } catch (error) {
      console.error("Error during CSV processing:", error);
      setErrorMessage(`An unexpected error occurred: ${error.message}. Please check the console for more details.`);
      setProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4 font-sans text-gray-800">
      <div className="bg-white p-8 rounded-lg shadow-lg w-full max-w-md text-center">
        <h1 className="text-3xl font-bold text-blue-600 mb-6">Monthly Reports Generator</h1>

        <p className="text-gray-600 mb-6">Upload your CSV file to generate separate monthly reports for each "Development Name??".</p>

        <div className="mb-6">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv"
            className="block w-full text-sm text-gray-500
                       file:mr-4 file:py-2 file:px-4
                       file:rounded-full file:border-0
                       file:text-sm file:font-semibold
                       file:bg-blue-50 file:text-blue-700
                       hover:file:bg-blue-100 cursor-pointer"
          />
          {selectedFile && (
            <p className="mt-2 text-sm text-gray-500">Selected file: <span className="font-medium">{selectedFile.name}</span></p>
          )}
        </div>

        <button
          onClick={processCsv}
          disabled={!selectedFile || processing}
          className={`w-full py-3 px-6 rounded-lg text-white font-semibold transition-all duration-300
                      ${!selectedFile || processing ? 'bg-blue-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 shadow-md'}`}
        >
          {processing ? (
            <div className="flex items-center justify-center">
              <svg className="animate-spin h-5 w-5 text-white mr-3" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {progressMessage || 'Processing...'}
            </div>
          ) : (
            'Generate Reports'
          )}
        </button>

        {errorMessage && (
          <p className="mt-4 text-red-600 text-sm">{errorMessage}</p>
        )}

        {downloadLink && (
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-700 font-semibold mb-3">Reports are ready!</p>
            <a
              href={downloadLink}
              download={`Monthly_Reports_${new Date().getFullYear()}-${(new Date().getMonth() + 1).toString().padStart(2, '0')}.zip`}
              className="inline-flex items-center justify-center px-5 py-2 border border-transparent text-base font-medium rounded-md text-white bg-green-600 hover:bg-green-700 transition-colors duration-200 shadow-sm"
              onClick={() => {
                // Clean up the object URL after download is initiated
                setTimeout(() => URL.revokeObjectURL(downloadLink), 100);
                setDownloadLink(null); // Clear the link after click
                setSelectedFile(null); // Clear selected file
                if (fileInputRef.current) {
                  fileInputRef.current.value = ''; // Clear file input visual
                }
              }}
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
              </svg>
              Download ZIP Archive
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
