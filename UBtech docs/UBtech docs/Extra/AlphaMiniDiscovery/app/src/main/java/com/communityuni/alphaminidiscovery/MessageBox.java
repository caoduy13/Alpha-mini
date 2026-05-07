package com.communityuni.alphaminidiscovery;

import android.app.AlertDialog;
import android.content.Context;
import android.widget.TextView;

import com.ubtrobot.transport.message.CallException;
import com.ubtrobot.transport.message.Request;
import com.ubtrobot.transport.message.Response;

public class MessageBox extends AlertDialog {
    Request request=null;
    Response response=null;
    CallException exception=null;

    TextView txtRequestId,txtRequestParam,txtRequestPath,txtRequestWhen;
    TextView txtResponetId,txtResponeParam,txtResponePath,txtResponeWhen;
    TextView txtError;

    public Request getRequest() {
        return request;
    }

    public void setRequest(Request request) {
        this.request = request;
    }

    public Response getResponse() {
        return response;
    }

    public void setResponse(Response response) {
        this.response = response;
    }

    public CallException getException() {
        return exception;
    }

    public void setException(CallException exception) {
        this.exception = exception;
    }

    protected MessageBox(Context context) {
        super(context);
        setContentView(R.layout.messagebox_layout);
        addControls();
    }
    public void showDialog() {
        if(request!=null)
        {
            txtRequestId.setText(request.getId());
            txtRequestParam.setText(request.getParam()+"");
            txtRequestPath.setText(request.getPath());
            txtRequestWhen.setText(request.getWhen()+"");
        }
        else
        {
            txtRequestId.setText("");
            txtRequestParam.setText("");
            txtRequestPath.setText("");
            txtRequestWhen.setText("");
        }
        if(response!=null)
        {
            txtResponetId.setText(response.getId());
            txtResponeParam.setText(response.getParam()+"");
            txtResponePath.setText(response.getPath());
            txtResponeWhen.setText(response.getWhen()+"");
        }
        else
        {
            txtResponetId.setText("");
            txtResponeParam.setText("");
            txtResponePath.setText("");
            txtResponeWhen.setText("");
        }
        if(exception!=null)
            txtError.setText(exception.getMessage());
        else
            txtError.setText("");
        show();
    }

    private void addControls() {
        txtRequestId=findViewById(R.id.txtRequestId);
        txtRequestParam=findViewById(R.id.txtRequestParam);
        txtRequestPath=findViewById(R.id.txtRequestPath);
        txtRequestWhen=findViewById(R.id.txtRequestWhen);
        txtResponetId=findViewById(R.id.txtResponetId);
        txtResponeParam=findViewById(R.id.txtResponeParam);
        txtResponePath=findViewById(R.id.txtResponePath);
        txtResponeWhen=findViewById(R.id.txtResponeWhen);
        txtError=findViewById(R.id.txtError);
    }
}
