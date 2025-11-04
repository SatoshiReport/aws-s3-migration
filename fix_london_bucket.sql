-- Fix london.satoshi.report bucket by removing directory markers

-- Step 1: Remove directory marker entries
DELETE FROM files 
WHERE bucket = 'london.satoshi.report' 
AND key LIKE '%/';

-- Step 2: Update bucket status with correct file count
UPDATE bucket_status 
SET file_count = 2377498,
    verify_complete = 0
WHERE bucket = 'london.satoshi.report';

-- Show the results
SELECT 'Updated bucket_status:' as info;
SELECT bucket, file_count, total_size, sync_complete, verify_complete, delete_complete 
FROM bucket_status 
WHERE bucket = 'london.satoshi.report';

SELECT 'Remaining files in database:' as info;
SELECT COUNT(*) as remaining_files 
FROM files 
WHERE bucket = 'london.satoshi.report';
