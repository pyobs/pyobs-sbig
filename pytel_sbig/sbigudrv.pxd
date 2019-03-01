from libcpp.string cimport string

cdef extern from "../src/csbigimg.h":
    ctypedef unsigned short MY_LOGICAL

    cdef cppclass CSBIGImg:
        CSBIGImg()
    
        void			Init()
        void			DeleteImageData()
    
        # Accessor Functions
        int				GetHeight()
        int				GetWidth()
        unsigned short	*GetImagePointer()
        #struct tm		GetImageStartTime()
        void			SetCCDTemperature(double temp)
        double			GetCCDTemperature()
        void			SetExposureTime(double exp)
        double			GetExposureTime()
        void			SetEachExposure(double exp)
        double			GetEachExposure()			
        void			SetFocalLength(double fl)	
        double			GetFocalLength()			
        void			SetApertureArea(double ap)	
        double			GetApertureArea()			
        void			SetResponseFactor(double resp)
        double			GetResponseFactor()	
        void			SetPixelHeight(double ht)
        double			GetPixelHeight()		
        void			SetPixelWidth(double wd)
        double			GetPixelWidth()	
        void			SetEGain(double gn)
        double			GetEGain()			
        void			SetBackground(long back)
        long			GetBackground()			
        void			SetRange(long range)	
        long			GetRange()				
        void			SetSaturationLevel(unsigned short sat)
        unsigned short	GetSaturationLevel()	
        void			SetNumberExposures(unsigned short no)
        unsigned short	GetNumberExposures()	
        void			SetTrackExposure(double exp)
        double			GetTrackExposure()		
        void			SetReadoutMode(unsigned short rm)
        unsigned short	GetReadoutMode()		
        void			SetPedestal(unsigned short ped)
        unsigned short	GetPedestal()			
        void			SetExposureState(unsigned short es)
        unsigned short	GetExposureState()		
        void			SetImageNote(string str)
        string			GetImageNote()			
        void			SetObserver(string str)	
        string			GetObserver()			
        void			SetHistory(string str)	
        string			GetHistory()			
        void			SetFilter(string str)	
        string			GetFilter()				
        void			SetSoftware(string str)	
        string			GetSoftware()			
        void			SetCameraModel(string str)
        string			GetCameraModel()		
        MY_LOGICAL		GetImageModified()
        void			SetImageModified(MY_LOGICAL isMod)
        #SBIG_IMAGE_FORMAT GetDefaultImageFormat()
        #void			SetDefaultImageFormat(SBIG_IMAGE_FORMAT fmt)
        MY_LOGICAL		GetImageCanClose()
        void			SetImageCanClose(MY_LOGICAL canDo)
    
        # More Accessor Functions
        void			SetImageStartTime()
        #void			SetImageStartTime(time_t startTime)
        void			SetImageStartTime(int mon, int dd, int yy, int hr, int min, int sec)
        #void			SetImageStartTime(struct tm *pStartTime)
        void			SetSubFrame(int nLeft, int nTop)
        void			GetSubFrame(int &nLeft, int &nTop)
        void			SetBinning(unsigned short nHoriz, unsigned short nVert)
        void			GetBinning(unsigned short &nHoriz, unsigned short &nVert)
        void			AddHistory(string str)
    
        # File IO Routines
        #SBIG_FILE_ERROR SaveImage(const char *pFullPath, SBIG_IMAGE_FORMAT fmt = SBIF_DEFAULT)
        #SBIG_FILE_ERROR OpenImage(const char *pFullPath)
    
        # Utility Functions
        MY_LOGICAL		AllocateImageBuffer(int height, int width)
        void			CreateSBIGHeader(char *pHeader, MY_LOGICAL isCompressed)
        MY_LOGICAL		ParseHeader(char *pHeader, MY_LOGICAL &isCompressed)
        #SBIG_FILE_ERROR SaveCompressedImage(const char *pFullPath, char *pHeader)
        #SBIG_FILE_ERROR ReadCompressedImage(FILE *fh)
        #SBIG_FILE_ERROR SaveUncompressedImage(const char *pFullPath, char *pHeader)
        #SBIG_FILE_ERROR ReadUncompressedImage(FILE *fh)
        int				CompressSBIGData(unsigned char *pCmpData, int imgRow)
        void			IntelCopyBytes(unsigned char *pRevData, int imgRow)
        void			AutoBackgroundAndRange()
        #string			GetFileErrorString(SBIG_FILE_ERROR err)
        unsigned short	GetAveragePixelValue()
        unsigned short	GetAveragePixelValue(int left, int top, int width, int height)
        void			GetFormattedImageInfo(string &iiStr, MY_LOGICAL htmlFormat)
    
        # Image Processing Funcions
        void			VerticalFlip()
        void			HorizontalFlip()
        #SBIG_FILE_ERROR DarkSubtract(CSBIGImg *pImg)
        #SBIG_FILE_ERROR FlatField(CSBIGImg *pImg)
        
        # Color Image Processing
        void			RemoveBayerColor()


cdef extern from "../src/csbigcam.h":
    cdef enum SBIG_DEVICE_TYPE:
        DEV_USB = 0x7F00

    ctypedef int PAR_ERROR

    ctypedef enum SBIG_DARK_FRAME:
        SBDF_LIGHT_ONLY, SBDF_DARK_ONLY, SBDF_DARK_ALSO

    cdef cppclass CSBIGCam:
        CSBIGCam(int type)

        void Init()

        # Error Reporting Routines
        PAR_ERROR 	GetError()
        #string 		GetErrorString()
        string 		GetErrorString(PAR_ERROR err)
        #PAR_COMMAND GetCommand()

        # Setters /Getters
        unsigned short GetFirmwareVersion()
        double GetExposureTime()
        void SetExposureTime(double exp)
        unsigned short GetReadoutMode()
        void SetReadoutMode(unsigned short rm)
        # CAMERA_TYPE GetCameraType()
        # ABG_STATE7 GetABGState()
        # void SetABGState(ABG_STATE7 abgState)
        void SetSubFrame(int nLeft,  int nTop,  int nWidth,  int nHeight)
        void GetSubFrame(int &nLeft, int &nTop, int &nWidth, int &nHeight)
        PAR_ERROR GetReadoutInfo(double &pixelWidth, double &pixelHeight, double &eGain)

        # Driver/Device Routines
        PAR_ERROR OpenDriver()
        PAR_ERROR CloseDriver()
        #PAR_ERROR OpenDevice(OpenDeviceParams odp)
        PAR_ERROR CloseDevice()
        #PAR_ERROR GetDriverInfo(DRIVER_REQUEST request, GetDriverInfoResults0 &gdir)

        # High-Level Exposure Related Commands
        PAR_ERROR GrabSetup(CSBIGImg *pImg, SBIG_DARK_FRAME dark)
        PAR_ERROR GrabMain (CSBIGImg *pImg, SBIG_DARK_FRAME dark)
        PAR_ERROR GrabImage(CSBIGImg *pImg, SBIG_DARK_FRAME dark)
        #void 	  GetGrabState(GRAB_STATE &grabState, double &percentComplete)

        # Low-Level Exposure Related Commands
        #PAR_ERROR StartExposure(SHUTTER_COMMAND shutterState)
        PAR_ERROR EndExposure()
        #PAR_ERROR IsExposureComplete(MY_LOGICAL &complete)
        #PAR_ERROR StartReadout(StartReadoutParams srp)
        PAR_ERROR EndReadout()
        #PAR_ERROR ReadoutLine(ReadoutLineParams rlp, MY_LOGICAL darkSubtract, unsigned short *dest)
        PAR_ERROR DumpLines(unsigned short noLines)

        # Temperature Related Commands
        PAR_ERROR GetCCDTemperature(double &ccdTemp)
        PAR_ERROR SetTemperatureRegulation(MY_LOGICAL enable, double setpoint)
        PAR_ERROR QueryTemperatureStatus(MY_LOGICAL &enabled, double &ccdTemp, double &setpointTemp, double &percentTE)

        # Control Related Commands
        #PAR_ERROR ActivateRelay(CAMERA_RELAY relay, double time)
        #PAR_ERROR IsRelayActive(CAMERA_RELAY relay, MY_LOGICAL &active)
        #PAR_ERROR AOTipTilt(AOTipTiltParams attp)
        #PAR_ERROR CFWCommand(CFWParams cfwp, CFWResults &cfwr)
        PAR_ERROR InitializeShutter()

        # General Purpose Commands
        PAR_ERROR EstablishLink()
        string 	  GetCameraTypeString()
        PAR_ERROR GetFullFrame(int &nWidth, int &nHeight)
        PAR_ERROR GetFormattedCameraInfo(string &ciStr, MY_LOGICAL htmlFormat)

        # Utility functions
        MY_LOGICAL 		CheckLink()
        unsigned short 	DegreesCToAD(double degC, MY_LOGICAL ccd)
        double 			ADToDegreesC(unsigned short ad, MY_LOGICAL ccd)

        # CFW Functions
        #CFW_MODEL_SELECT	GetCFWModel() { return m_eCFWModel; }
        #PAR_ERROR 			SetCFWModel(CFW_MODEL_SELECT cfwModel, CFW_COM_PORT comPort = CFWPORT_COM1)
        #PAR_ERROR 			SetCFWPosition(CFW_POSITION position)
        #PAR_ERROR 			GetCFWPositionAndStatus(CFW_POSITION &position, CFW_STATUS &status)
        #PAR_ERROR 			GetCFWMaxPosition(CFW_POSITION &position)
        #CFW_ERROR 			GetCFWError() { return m_eCFWError; }
        #string 				GetCFWErrorString(CFW_ERROR err)
        string 				GetCFWErrorString()

        # Allows access directly to driver
        PAR_ERROR SBIGUnivDrvCommand(short command, void *Params, void *Results)
